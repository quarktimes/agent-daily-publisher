"""
Title Agent — Generates and selects the best article title.

Strategy: generate 3-5 candidates, score each, pick the best.
This avoids the "one-shot title gamble" where the LLM produces
a boring title and we're stuck with it.
"""

import re
from typing import Any

from core.agent import BaseAgent, AgentContext

TITLE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "article_title": {"type": "string"},
        "article_content": {"type": "string"},
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["article_content"],
}

TITLE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
            },
        },
        "strategy": {"type": "string"},
    },
    "required": ["title", "candidates"],
}

# Scoring rubric for title quality
_SCORING_RULES = """
## 评分标准（每候选标题独立评分 0-100）

### 加分项

| 特征 | 加分 | 示例 |
|------|------|------|
| 含具体数字/百分比 | +15 | "从 8% 到 0"、"3 层管道"、"1 行代码" |
| 技术名词精准 | +10 | "ReAct"、"Jinja2"、"MCP"、"Tool Calling"、"PgVector" |
| 制造认知冲突 | +20 | "放弃死磕 Prompt，改用___"、"所有人都说___，但我不这么认为" |
| 结果可量化 | +15 | "渲染崩溃归零"、"P99 降 90%"、"错误率降至 0.1%" |
| 标题 ≤30 字 | +5 | |
| 有悬念/好奇心 | +10 | "为什么我不再____"、"当____时，我做了____" |
| 具体场景 | +10 | 读者看完知道文章在讲什么 |

### 扣分项

| 特征 | 扣分 | 示例 |
|------|------|------|
| 纯日期/纯描述 | -50 | "技术日报 | 2026-06-14" |
| 太长 >45 字 | -15 | |
| 无技术名词 | -10 | "一个问题的修复过程" |
| 空洞/不具体 | -20 | "今天的工作总结"、"重要发现" |
| 像章节标题 | -30 | "### 背景与问题" |

### 高分模版参考

- "放弃死磕 Prompt，我用 Jinja2 管道将格式错误率降至 0.1%" → 数字+技术名词+冲突+可量化 = 95+
- "从 8% 到 0：一个正则拯救了 Markdown 渲染" → 数字+结果+具体 = 90+
- "LLM 写代码很行，写文档？不行。" → 冲突+好奇 = 85+
"""


class TitleAgent(BaseAgent):
    """
    Generates and selects the optimal article title.

    Agent Pattern: Generate-Score-Select
      - Generates 3-5 diverse candidates
      - Scores each against a rubric
      - Returns the highest-scoring title
    """

    agent_name = "title"
    output_schema = TITLE_OUTPUT_SCHEMA
    input_schema = TITLE_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        old_title = input_data.get("article_title", "")
        return f"""你是**标题的最终决策者**。其他 Agent 写的标题仅供参考，你拥有标题的最终决定权。

文章原标题（仅供参考，可以不参考）：{old_title}

## 三选策略

必须生成 3 个不同角度的标题：

1. **冲突型** — "放弃死磕 Prompt，我用 Jinja2 管道将格式错误率降至 0.1%"
2. **好奇型** — "为什么我不再调 Prompt 了？因为一行正则搞定了"
3. **结果型** — "从 8% 到 0：一个 Python 脚本拯救了 Markdown 渲染"

{_SCORING_RULES}

## 输出流程

1. 阅读文章内容，提取 1-2 个最核心的技术亮点（有数字的 > 没数字的）
2. 用提取的亮点生成 3 个不同角度的标题
3. 按评分标准给每个标题打分
4. 选出最高分的标题

## 输出 JSON

{{
  "title": "最高分的标题",
  "candidates": [
    {{"title": "...", "score": 90, "reason": "数字+冲突+技术名词"}},
    {{"title": "...", "score": 75, "reason": "有悬念但有技术名词"}}
  ],
  "strategy": "conflict / curiosity / result"
}}

不要输出任何其他内容。
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        title = output.get("title", "").strip()
        if not title or len(title) < 5:
            # Fallback: use original title
            title = ctx.input.get("article_title", "技术复盘")
            output["title"] = title
        output["title"] = title[:80]
        return output
