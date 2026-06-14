"""
Article Format Sanitizer — Normalize LLM-generated markdown to a consistent style.

Fixes common LLM formatting issues:
  1. Inconsistent heading levels (### vs ## vs bold text)
  2. Messy code blocks (wrong lang, no lang, inconsistent spacing)
  3. Inconsistent list markers (- vs * vs • vs 1.)
  4. Trailing whitespace, extra blank lines
  5. Emoji inconsistency
  6. Inline code formatting

This runs as a post-processor AFTER generation, BEFORE publishing.
"""

import re
from typing import Any


def sanitize_article(article: dict[str, Any]) -> dict[str, Any]:
    """Normalize an article's content field to consistent style."""
    content = article.get("content", "")
    if not content:
        return article

    article["content"] = _normalize_markdown(content)
    if article.get("title"):
        article["title"] = _clean_title(article["title"])
    if article.get("summary"):
        article["summary"] = _clean_summary(article["summary"])
    return article


def _normalize_markdown(text: str) -> str:
    """Apply all normalization rules."""
    rules = [
        _fix_broken_fences,          # Strip/fix garbage ``` lines before anything else
        _fix_unclosed_code_blocks,   # Close unclosed fences
        _fix_code_blocks,
        _fix_headings,
        _fix_lists,
        _fix_blank_lines,
        _fix_trailing_whitespace,
        _fix_inline_code,
        _fix_tables,
    ]
    result = text
    for rule in rules:
        result = rule(result)
    return result.strip() + "\n"


def _fix_broken_fences(text: str) -> str:
    """Fix lines where ``` is followed by non-language content.

    Valid: ```   ```python   ```mermaid
    Invalid: ```### heading   ```**bold**   ```python\ncode   ```'):
    """
    import re

    def _fix_line(line):
        stripped = line.strip()
        if not stripped.startswith("```"):
            return line
        # Already valid: ``` alone or ```lang
        if re.match(r'^```[a-zA-Z0-9_+#.-]*$', stripped):
            return line
        # Broken: ``` followed by content — try to extract heading or strip
        after_fence = stripped[3:].lstrip()
        if not after_fence:
            return "```"
        # If it's clearly markdown content (headings, text), treat as regular line
        if re.match(r'^[#*\-\d]', after_fence):
            return after_fence  # Strip the ```  prefix
        if after_fence.startswith("**"):
            return after_fence  # Strip ```
        # If it has code-like content, try to separate
        if "\n" in after_fence:
            # ```python\ncode... → becomes ```python plus code lines
            first, rest = after_fence.split("\n", 1)
            if re.match(r'^[a-zA-Z0-9_+#.-]+$', first):
                return "```" + first + "\n" + rest + "\n```"
            return after_fence
        # Last resort: strip ALL ``` occurrences from this line (it's broken markdown)
        return re.sub(r'```', '', after_fence)

    lines = text.split("\n")
    result = [_fix_line(line) for line in lines]
    return "\n".join(result)


def _fix_unclosed_code_blocks(text: str) -> str:
    """Ensure every opening ``` has a matching closing ```.

    If a code fence is never closed, the rest of the article becomes
    one giant code block — the most destructive formatting bug.
    """
    lines = text.split("\n")
    in_code = False
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Fence check: ``` alone, or ``` followed ONLY by a language tag (no spaces, no other text)
        is_fence = (
            stripped == "```"
            or bool(re.match(r'^```[a-zA-Z0-9_+#.-]+$', stripped))
            or bool(re.match(r'^```\s*$', stripped))  # bare ``` with optional trailing spaces
        )

        if is_fence and not in_code:
            in_code = True
            result.append(line)
        elif is_fence and in_code:
            # Check if this is a close or a new block
            in_code = False
            result.append(line)
        elif not is_fence:
            result.append(line)

    # If we ended with an unclosed code block, close it
    if in_code:
        result.append("```")

    return "\n".join(result)


def _fix_code_blocks(text: str) -> str:
    """Ensure all code blocks have language tags and consistent spacing."""
    def _normalize_block(match):
        lang = match.group(1).strip() or "text"
        code = match.group(2)
        # Remove leading/trailing blank lines in code
        code = code.strip()
        # Normalize indentation to 4 spaces
        lines = code.split("\n")
        normalized = []
        for line in lines:
            # Convert tabs to spaces
            line = line.replace("\t", "    ")
            # Strip trailing whitespace
            line = line.rstrip()
            normalized.append(line)
        return f"\n```{lang}\n" + "\n".join(normalized) + "\n```\n"

    return re.sub(r'```(\w*)\s*\n(.*?)```', _normalize_block, text, flags=re.DOTALL)


def _fix_headings(text: str) -> str:
    """Normalize heading levels and style."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        # Convert bold text used as headings to proper headings
        if stripped.startswith("**") and stripped.endswith("**") and len(stripped) < 80:
            inner = stripped[2:-2].strip()
            if inner and not inner.startswith("#"):
                result.append(f"### {inner}")
                continue
        # Ensure exactly one space after #, skip if next char is # (higher-level heading)
        for level in range(1, 5):
            prefix = "#" * level
            if stripped.startswith(prefix) and len(stripped) > level:
                next_char = stripped[level]
                if next_char == "#":
                    continue  # This is a higher-level heading, try next level
                if next_char != " ":
                    line = prefix + " " + stripped[level:]
                else:
                    line = prefix + " " + stripped[level:].lstrip()
                break
        result.append(line)
    return "\n".join(result)


def _fix_lists(text: str) -> str:
    """Normalize list markers to consistent style."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        # Unify list markers: • → -
        if stripped.startswith("• "):
            line = indent + "- " + stripped[2:]
        elif stripped.startswith("* ") and not stripped.startswith("**"):
            line = indent + "- " + stripped[2:]
        result.append(line)
    return "\n".join(result)


def _fix_blank_lines(text: str) -> str:
    """Remove excessive blank lines (max 1 consecutive)."""
    return re.sub(r'\n{3,}', '\n\n', text)


def _fix_trailing_whitespace(text: str) -> str:
    """Strip trailing whitespace from every line."""
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _fix_inline_code(text: str) -> str:
    """Ensure consistent inline code formatting."""
    # Fix inline code with extra spaces: ` code ` → `code`
    result = re.sub(r'`\s+([^`]+?)\s+`', r'`\1`', text)
    # Fix bold with inconsistent spacing: ** text ** → **text**
    result = re.sub(r'\*\*\s+([^*]+?)\s+\*\*', r'**\1**', result)
    return result


def _fix_tables(text: str) -> str:
    """Ensure tables have proper formatting."""
    lines = text.split("\n")
    result = []
    in_table = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        is_table_row = stripped.startswith("|") and stripped.endswith("|")
        is_separator = bool(re.match(r'^\|[\s\-:|]+\|$', stripped))

        if is_table_row or is_separator:
            in_table = True
            # Ensure pipes have spaces: |A|B| → | A | B |
            if not is_separator:
                cells = stripped.split("|")
                cells = [c.strip() for c in cells[1:-1]]
                line = "| " + " | ".join(cells) + " |"
        else:
            if in_table and stripped:
                result.append("")  # blank line after table
            in_table = False
        result.append(line)
    return "\n".join(result)


def _clean_title(title: str) -> str:
    """Clean article title."""
    # Remove excessive colons
    title = re.sub(r'：{2,}', '：', title)
    title = re.sub(r':{2,}', ': ', title)
    # Remove trailing punctuation
    title = title.rstrip("，。！？,.!?")
    # Ensure reasonable length
    if len(title) > 80:
        title = title[:77] + "..."
    return title.strip()


def _clean_summary(summary: str) -> str:
    """Clean article summary."""
    # Remove markdown formatting
    summary = re.sub(r'[#*`>]', '', summary)
    # One sentence or two max
    sentences = re.split(r'[。！？]', summary)
    if len(sentences) > 2:
        summary = "。".join(sentences[:2]) + "。"
    return summary.strip()
