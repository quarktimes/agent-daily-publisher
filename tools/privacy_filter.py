"""
Privacy Filter — Sanitize session data and validate article content.

Two-stage protection:
  Stage 1 — Input Sanitization: Strip sensitive patterns from session data
    BEFORE sending to the LLM (prevent secrets from appearing in articles)

  Stage 2 — Output Validation: Scan generated articles for remaining sensitive
    content BEFORE publishing (last line of defense)

This runs inline in the pipeline, not as a separate agent. It's a guardrail,
not a decision-maker.
"""

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# Patterns that indicate sensitive information
SENSITIVE_PATTERNS: list[re.Pattern] = [
    # API Keys / Tokens
    re.compile(r'sk-[A-Za-z0-9]{20,}'),               # OpenAI keys
    re.compile(r'ghp_[A-Za-z0-9]{36,}'),               # GitHub PAT
    re.compile(r'gho_[A-Za-z0-9]{36,}'),               # GitHub OAuth
    re.compile(r'ghu_[A-Za-z0-9]{36,}'),               # GitHub user token
    re.compile(r'xox[baprs]-[A-Za-z0-9\-]{24,}'),      # Slack tokens
    re.compile(r'8CKv[A-Za-z0-9]{20,}'),               # Dev.to / known key pattern
    re.compile(r'AKIA[A-Z0-9]{16}'),                   # AWS Access Key

    # Connection strings
    re.compile(r'jdbc:(mysql|postgresql|sqlite|h2|oracle|mariadb)://[^\s"\']+'),
    re.compile(r'mongodb://[^\s"\']+@[^\s"\']+'),
    re.compile(r'redis://[^@]+@[^\s"\']+'),
    re.compile(r'postgresql://[^@]+@[^\s"\']+'),
    re.compile(r'mysql://[^@]+@[^\s"\']+'),

    # Private keys
    re.compile(r'-----BEGIN (RSA|EC|OPENSSH|DSA|PRIVATE) KEY-----'),

    # IP addresses (potential internal hosts — only flag common patterns)
    re.compile(r'(?<!\d)(10\.\d{1,3}\.\d{1,3}\.\d{1,3})(?!\d)'),
    re.compile(r'(?<!\d)(172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?!\d)'),
    re.compile(r'(?<!\d)(192\.168\.\d{1,3}\.\d{1,3})(?!\d)'),
]

# Patterns to REDACT in session data (Stage 1)
# These get replaced with [REDACTED] before the LLM sees them
REDACT_PATTERNS: list[re.Pattern] = [
    re.compile(r'(password|passwd|pwd)\s*[:=]\s*["\']?[^\s"\'&,;]+["\']?', re.IGNORECASE),
    re.compile(r'(secret|api_key|apikey|api\.key)\s*[:=]\s*["\']?[A-Za-z0-9_\-]{8,}["\']?', re.IGNORECASE),
    re.compile(r'(token|access_token|refresh_token)\s*[:=]\s*["\']?[A-Za-z0-9_\-.\/]{8,}["\']?', re.IGNORECASE),
    re.compile(r'(connection\.string|connstr)\s*[:=]\s*["\']?[^\s"\'&,;]+["\']?', re.IGNORECASE),
]

# Redacted config values in generated text (key=value patterns)
CONFIG_VALUE_PATTERN = re.compile(
    r'(spring\.(datasource|redis|mail|cloud)|'
    r'mybatis\.|'
    r'jdbc\.|'
    r'redis\.|'
    r'database\.|'
    r'db\.)'
    r'[\w.]*\s*[=:]\s*.+',
    re.IGNORECASE
)


def sanitize_input(data: Any) -> Any:
    """
    Stage 1: Remove sensitive patterns from session data before LLM processing.

    Scans all string values in the input data (dict/list nesting) and
    redacts sensitive patterns. This prevents secrets from ever reaching
    the Write/Adapt agents.
    """
    import copy

    if isinstance(data, str):
        return _redact_string(data)
    elif isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(sanitize_input(item) for item in data)
    return data


def _redact_string(text: str) -> str:
    """Redact sensitive patterns from a single string."""
    result = text
    for pattern in REDACT_PATTERNS:
        result = pattern.sub(r'\1: [REDACTED]', result)
    # Also redact standalone secrets
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub('[REDACTED]', result)
    return result


def scan_article(article: dict[str, Any]) -> list[dict]:
    """
    Stage 2: Scan a generated article for remaining sensitive content.

    Returns a list of findings. Empty list = clean.
    Each finding: {field, pattern, snippet}
    """
    findings = []
    text_fields = ["title", "content", "summary"]

    for field in text_fields:
        text = article.get(field, "")
        if not isinstance(text, str):
            continue

        for pattern in SENSITIVE_PATTERNS:
            for match in pattern.finditer(text):
                findings.append({
                    "field": field,
                    "pattern": pattern.pattern[:30],
                    "snippet": _surrounding_text(text, match.start(), 40),
                })

        # Check for leaked config values
        for match in CONFIG_VALUE_PATTERN.finditer(text):
            findings.append({
                "field": field,
                "pattern": "config_value",
                "snippet": _surrounding_text(text, match.start(), 50),
            })

    return findings


def _surrounding_text(text: str, pos: int, context: int = 40) -> str:
    """Get text surrounding a position for context."""
    start = max(0, pos - context)
    end = min(len(text), pos + context)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def validate_article_safe(article: dict[str, Any]) -> tuple[bool, list[dict]]:
    """
    Validate that an article is safe to publish.

    Returns: (is_safe, findings)
    """
    findings = scan_article(article)
    if findings:
        logger.warning(f"Privacy check FAILED: {len(findings)} findings")
        for f in findings:
            logger.warning(f"  [{f['field']}] {f['snippet']}")
        return False, findings

    logger.info("Privacy check PASSED")
    return True, []


def add_privacy_instruction_to_prompt(base_prompt: str) -> str:
    """Append privacy instructions to an agent's system prompt."""
    return base_prompt + """

## PRIVACY & SECURITY — CRITICAL
You MUST NOT include any of the following in your output:
  - API keys, tokens, passwords, or secrets of any kind
  - Database connection strings or URLs (jdbc:, mysql://, redis://, etc.)
  - Internal IP addresses (10.x, 172.16-31.x, 192.168.x)
  - Configuration files with actual values (spring.datasource, etc.)
  - Private keys or certificates
  - Cloud service credentials (AWS keys, etc.)

If the input data contains any of the above, either omit it entirely or
replace it with a generic description (e.g., "configured database connection"
not "jdbc:mysql://user:pass@10.0.0.1:3306/db").
Focus on the engineering decisions, not the specific configuration values.
"""
