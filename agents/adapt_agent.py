"""
Adapt Agent — Translates articles between languages for multi-platform publishing.

Rules:
  - Title: TRANSLATE only. Never rewrite. TitleAgent is the sole style authority.
  - Content: FULL translation paragraph by paragraph. Never omit or add content.
  - Code blocks: preserve ALL code. Translate only comments.
  - Technical claims, numbers, metrics: must be IDENTICAL across languages.
"""

from typing import Any
from core.agent import BaseAgent, AgentContext

ADAPT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "article": {"type": "object"},
        "platforms": {"type": "array"},
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
    agent_name = "adapt"
    output_schema = ADAPT_OUTPUT_SCHEMA
    input_schema = ADAPT_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        platforms = input_data.get("platforms", [])
        platform_desc = "\n".join(
            f"  - {p.get('name', 'unknown')}: {p.get('language', 'zh')}"
            for p in platforms
        )
        return f"""你是翻译 Agent。翻译文章到指定语言。

目标平台：{platform_desc}

## 核心规则（必须遵守）

### 标题
- **只翻译，不改写**。原文标题的意思不能变
- 不要优化、不要润色、不要"让它更吸引人"
- TitleAgent 是标题风格的唯一决策者

### 内容
- 逐段翻译，不省略、不增加
- 代码块：保留全部代码，注释翻译
- 技术名词（ReAct、MCP、PgVector 等）：保持原文
- 数字、指标、URL：原样保留

### 格式
- 保留原文所有 Markdown 格式（标题层级、列表、表格、代码块）
- 不改变文章结构

## 各平台说明

### Dev.to
- 语言：英文
- 标题：英译，保持原意

### 微信公众号
- 语言：中文
- 标题：保持原标题

### 掘金
- 语言：中文
- 标题：保持原标题

返回 JSON：{{"versions": [{{"platform": "...", "title": "...", "content": "...", "tags": [...], "language": "zh/en"}}]}}
"""
