"""
Write Agent — Generation with Constraints Pattern

This agent demonstrates controlled generation:
  1. Takes structured analysis data
  2. Renders it into an engaging, well-structured article
  3. Follows platform-specific style guidelines
  4. Maintains technical accuracy while being accessible

The constraint is the key: the agent must balance
technical depth with readability, and follow a template
without sounding templated.
"""

from datetime import datetime
from typing import Any

from core.agent import BaseAgent, AgentContext

WRITE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "day_summary": {"type": "string"},
        "highlights": {"type": "array"},
        "architecture_decisions": {"type": "array"},
        "key_insights": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "themes": {"type": "array"},
        "previous_feedback": {"type": "object"},
        "iteration": {"type": "integer"},
    },
    "required": ["date", "day_summary", "highlights", "key_insights"],
}

WRITE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "content", "tags"],
}


class WriteAgent(BaseAgent):
    """
    Generates engaging technical blog articles from structured analysis.

    Agent Pattern: Generation with Constraints
      - Follows narrative structure (problem → solution → impact)
      - Adheres to style guidelines without sounding robotic
      - Includes code snippets with context
      - Respects platform-specific conventions
    """

    agent_name = "write"
    output_schema = WRITE_OUTPUT_SCHEMA
    input_schema = WRITE_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        iteration = input_data.get("iteration", 1)
        previous_feedback = input_data.get("previous_feedback")

        feedback_section = ""
        if previous_feedback and iteration > 1:
            feedback_section = f"""
REVISION ITERATION {iteration}

Previous feedback to address:
  - Score: {previous_feedback.get('score', 'N/A')}
  - Feedback: {previous_feedback.get('feedback', [])}

Please address each feedback point in your revision.
"""

        return f"""You are a technical blog writer. Your job is to turn structured analysis data into an engaging, well-written technical article.

Date: {date}
{feedback_section}

Article structure:

## 📌 今日概述
- A 2-3 sentence summary of what was accomplished today
- Set the context for readers

## 🔧 问题和方案
For each highlight (especially problems/solutions):
- **背景**: Set up the context so any developer can understand
- **根因分析**: Explain WHY it happened (this is the most valuable part for readers)
- **方案**: Show the solution with code if applicable
- **效果**: Quantify the impact if possible

## 🏗 架构决策
For each architecture decision:
- What was decided
- What alternatives were considered
- Why this choice won

## 💡 关键收获
- Lessons that apply beyond today's work
- Pattern-level insights

Writing guidelines:
  - Lead with value: start each section with what the reader will learn
  - Be specific: "Fixed N+1 query" not "Fixed performance issue"
  - Show code: use markdown code blocks when code is discussed
  - Explain the "why": the decision rationale is more valuable than the decision
  - Keep it real: write like an experienced engineer, not a marketing copy
  - Length: 800-1500 words is ideal for technical articles

Platform: universal (will be adapted per-platform later)
Language: Chinese (中文) — use a mix of Chinese and technical English terms naturally

Return your response as a JSON object with:
  - title: catchy, descriptive title (include date)
  - content: the full markdown article
  - summary: 2-3 sentence summary for social sharing
  - tags: 3-5 relevant tags
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Ensure minimum content quality."""
        content = output.get("content", "")
        if len(content.strip()) < 100:
            ctx.error = "Generated content too short"
            raise ValueError(f"Article content is only {len(content)} characters")

        # Ensure title is present
        if not output.get("title"):
            output["title"] = f"技术日报 | {ctx.input.get('date', datetime.now().strftime('%Y-%m-%d'))}"

        return output
