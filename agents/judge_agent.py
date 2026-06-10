"""
Judge Agent — Self-Evaluation Pattern

This agent demonstrates the Self-Evaluation (Critic) pattern:
  1. Takes an article as input
  2. Evaluates it across multiple quality dimensions
  3. Provides actionable feedback for improvement
  4. Makes a pass/fail decision based on configurable thresholds

The self-evaluation loop is a hallmark of production agent systems.
Without it, agents produce unchecked output that degrades over time.
"""

from typing import Any

from core.agent import BaseAgent, AgentContext

JUDGE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "article": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
        "iteration": {"type": "integer"},
    },
    "required": ["article"],
}

JUDGE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "dimensions": {
            "type": "object",
            "properties": {
                "technical_accuracy": {"type": "integer", "minimum": 0, "maximum": 100},
                "clarity": {"type": "integer", "minimum": 0, "maximum": 100},
                "engagement": {"type": "integer", "minimum": 0, "maximum": 100},
                "structure": {"type": "integer", "minimum": 0, "maximum": 100},
                "actionability": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": ["technical_accuracy", "clarity", "engagement", "structure"],
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "feedback": {"type": "array", "items": {"type": "string"}},
        "verdict": {"type": "string", "enum": ["pass", "revise", "reject"]},
        "suggested_title": {"type": "string"},
    },
    "required": ["score", "dimensions", "verdict", "feedback"],
}


class JudgeAgent(BaseAgent):
    """
    Evaluates article quality and provides improvement feedback.

    Agent Pattern: Self-Evaluation (Critic)
      - Multi-dimensional quality scoring
      - Actionable feedback generation
      - Configurable pass/fail thresholds
      - Enables the revision loop (critic -> generator -> critic)
    """

    agent_name = "judge"
    output_schema = JUDGE_OUTPUT_SCHEMA
    input_schema = JUDGE_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        iteration = input_data.get("iteration", 1)
        return f"""You are a Judge Agent that evaluates technical blog articles for quality and completeness.

Evaluation iteration: {iteration}

Evaluate the article across these dimensions (0-100):

1. technical_accuracy: Are technical claims correct? Is code accurate?
2. clarity: Is the article easy to understand?
3. engagement: Would a developer want to read this?
4. structure: Is the article well-organized?
5. actionability (bonus): Does the reader learn something they can use?

Verdict rules:
  - pass: score >= 70 AND no dimension below 60
  - revise: score >= 50 or one weak dimension
  - reject: score < 50 or critical errors

Feedback: be specific, constructive, prioritized.

CRITICAL OUTPUT FORMAT:
You MUST respond with ONLY a raw JSON object. No markdown, no tables, no code fences, no explanation.
The JSON must have keys: score, dimensions (with technical_accuracy, clarity, engagement, structure), strengths, weaknesses, feedback, verdict, suggested_title

Example:
{{"score": 82, "dimensions": {{"technical_accuracy": 90, "clarity": 80, "engagement": 75, "structure": 85}}, "feedback": ["Add root cause analysis"], "verdict": "revise", "strengths": ["Good examples"], "weaknesses": ["Missing context"], "suggested_title": "fix"}}

Do NOT include any text outside the JSON object.
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Ensure verdict consistency with score."""
        score = output.get("score", 0)
        verdict = output.get("verdict", "revise")

        if score >= 70 and verdict == "reject":
            output["verdict"] = "pass"
        elif score < 50 and verdict == "pass":
            output["verdict"] = "reject"

        return output
