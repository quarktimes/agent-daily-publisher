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

        return f"""你是 Adapt Agent。输入包含结构化字段（background、root_causes、solutions、decisions、takeaways等）和已渲染的中文 Markdown。你的任务是从**结构化字段**出发，为不同平台生成独立内容，而不是翻译中文 Markdown。

目标平台：{platform_desc}

## 核心原则

1. **从结构化数据生成，不翻译** — 中文 Markdown 仅供参考。从 `background.problem`、`solutions[0].code_after`、`takeaways` 等结构化字段直接生成平台内容
2. **技术准确性一致** — 代码、技术名词、数字、trade-off 声明必须与原始结构化数据完全一致
3. **"原生感"** — 每篇读起来像原生于那个平台，不是从另一种语言翻译过来的

## 平台要求

### 微信公众号
- 语言：中文
- 风格：对话感，像在给朋友讲今天做的事
- 代码：精简到 1-2 个关键片段，大段代码概括为 "核心逻辑是..."
- 标题：20 字以内，吸引点击但不标题党
- 段落：每段 ≤3 行，短句为主
- 篇幅：800-1200 字
- 禁止：大段代码、长段落、多级嵌套标题

### Dev.to （与微信公众号内容必须一致，仅语言不同）
- 语言：英文
- 风格：Practical tutorial / Lessons learned
- 代码：保留全部代码块，注释翻译成英文
- 标签：3-4 个小写英文
- 篇幅：800-1500 字
- 标题：直接、有悬念
- **关键要求**：内容结构、案例、代码、技术要点必须与中文版完全一致。只改变语言，不改变内容

## 输出
返回 JSON：{{"versions": [{{"platform": "wechat_mp/devto", "title": "...", "content": "...", "tags": [...], "language": "zh/en"}}]}}
"""
