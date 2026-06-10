"""
Analyze Agent — Chain-of-Thought Pattern

This agent demonstrates the Chain-of-Thought (CoT) pattern:
  1. Takes raw session data (multiple sessions, varied topics)
  2. Reasons step-by-step through the day's work
  3. Identifies patterns: what problems were solved, what decisions made
  4. Extracts deep insights, not surface-level summaries

The CoT pattern enables the agent to:
  - Separate signal from noise across many sessions
  - Connect related work that happened in separate sessions
  - Infer root causes from conversations about symptoms
"""

from typing import Any

from core.agent import BaseAgent, AgentContext

ANALYZE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "sessions": {"type": "array"},
        "total_prompts": {"type": "integer"},
        "projects": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["date", "sessions"],
}

ANALYZE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "day_summary": {"type": "string"},
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "description": {"type": "string"},
                    "related_projects": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["problem", "solution", "decision", "insight", "achievement"]},
                    "title": {"type": "string"},
                    "context": {"type": "string"},
                    "root_cause": {"type": "string"},
                    "solution": {"type": "string"},
                    "impact": {"type": "string"},
                    "code_snippet": {"type": "string"},
                },
                "required": ["type", "title"],
            },
        },
        "architecture_decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string"},
                    "rationale": {"type": "string"},
                    "alternatives": {"type": "string"},
                    "tradeoffs": {"type": "string"},
                },
            },
        },
        "key_insights": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["date", "day_summary", "highlights", "key_insights"],
}


class AnalyzeAgent(BaseAgent):
    """
    Analyzes raw session data to extract structured technical insights.

    Agent Pattern: Chain-of-Thought
      - Reasons step-by-step through session data
      - Identifies cross-session patterns
      - Extracts root causes, not just symptoms
      - Categorizes work into meaningful themes
    """

    agent_name = "analyze"
    output_schema = ANALYZE_OUTPUT_SCHEMA
    input_schema = ANALYZE_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        session_count = len(input_data.get("sessions", []))
        return f"""You are an Analyze Agent that extracts structured technical insights from Claude Code session data.

Date to analyze: {date}
Sessions captured: {session_count}

Instructions — think step-by-step:

STEP 1 — Scan: Read through all sessions. What broad categories of work happened today?
STEP 2 — Identify problems: For each technical problem, extract:
  - What was the actual issue? (not just the symptom)
  - What was the root cause?
  - How was it solved?
STEP 3 — Extract decisions: What architectural or design decisions were made? Why?
STEP 4 — Find connections: Are there themes or insights that span multiple sessions?
STEP 5 — Quantify: What was the impact? (bugs fixed, features built, perf improved)

Output rules:
  - Each highlight must have a clear "type": problem | solution | decision | insight | achievement
  - For problems, ALWAYS include root_cause — if not obvious, infer it
  - Architecture decisions must include rationale and tradeoffs
  - key_insights should be lessons that apply beyond today's specific work
  - Tags should be broad categories (e.g., "backend", "frontend", "devops", "AI", "bug-fix")

Quality standards:
  - Be specific: "Fixed N+1 query in UserService.findByOrg()" not "Fixed performance issue"
  - Be accurate: only extract what the session data supports
  - Be insightful: connect dots across sessions when possible
"""
