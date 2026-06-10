"""
Adapt Agent — Transformation Pattern

This agent demonstrates content transformation:
  1. Takes a universal article
  2. Adapts it for each platform's style and constraints
  3. Handles language differences (zh/en)
  4. Optimizes for each platform's audience

The transformation pattern is essential for multi-channel publishing.
Without it, articles read the same on every platform, missing
each platform's unique strengths.
"""

from typing import Any

from core.agent import BaseAgent

ADAPT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "article": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "summary": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
        "platforms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "language": {"type": "string"},
                    "audience": {"type": "string"},
                },
            },
        },
    },
    "required": ["article", "platforms"],
}

ADAPT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "versions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "language": {"type": "string"},
                },
                "required": ["platform", "title", "content", "tags"],
            },
        },
    },
    "required": ["versions"],
}


class AdaptAgent(BaseAgent):
    """
    Adapts articles for different platform audiences.

    Agent Pattern: Transformation
      - Content style transfer between platforms
      - Multi-language adaptation (Chinese/English)
      - Audience-aware tone and depth adjustment
      - Platform constraint handling (tag limits, length limits)
    """

    agent_name = "adapt"
    output_schema = ADAPT_OUTPUT_SCHEMA
    input_schema = ADAPT_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        platforms = input_data.get("platforms", [])
        platform_desc = "\n".join(
            f"  - {p.get('name', 'unknown')}: language={p.get('language', 'zh')}, "
            f"audience={p.get('audience', 'developers')}"
            for p in platforms
        )

        return f"""You are an Adapt Agent that transforms articles for different platforms.

Target platforms:
{platform_desc}

For each platform, adapt the article:

1. **掘金 (Juejin)** — Chinese, developers
   - Technical depth: HIGH
   - Keep code examples, add more technical detail
   - Chinese language with English technical terms
   - Tags: 3-5 Chinese tags
   - Length: 1000-2000 words

2. **Dev.to** — English, global developers
   - Technical depth: MEDIUM-HIGH
   - Full English translation
   - Focus on practical, actionable content
   - Tags: max 4, lowercase
   - Length: 800-1500 words

3. **Medium** — English, broader tech audience
   - Technical depth: MEDIUM
   - Add narrative arc: problem → journey → solution → insight
   - Fewer code blocks, more conceptual explanation
   - Length: 600-1200 words

4. **知乎 (Zhihu)** — Chinese, deep thinking audience
   - Technical depth: HIGH
   - Focus on principles and methodology over code
   - Add comparisons with alternative approaches
   - Length: 1000-2000 words

5. **微信公众号** — Chinese, mobile-first
   - Technical depth: LOW-MEDIUM
   - Simplify code, focus on concepts
   - Shorter paragraphs, more whitespace
   - Friendly, conversational tone
   - Length: 800-1200 words

General rules:
  - Preserve all technical claims and code correctness
  - Adjust the title for each platform's style
  - Return one version per platform
  - Each version must be a complete, publishable article
  - Do NOT include the instruction text in the output
"""
