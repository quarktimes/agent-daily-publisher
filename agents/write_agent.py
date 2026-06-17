"""
Write Agent — Outputs clean Markdown content. No more flat string parsing.

The LLM outputs a full Markdown article as the `content` field.
No _parse_solution, _parse_root_cause — all deleted.
TemplateRenderer still handles the Markdown template for Dev.to.
WeChatRenderer handles Markdown → WeChat HTML via MD2WeChat.
"""

from typing import Any
from core.agent import BaseAgent, AgentContext

INPUT_SCHEMA = {
    "type": "object", "properties": {
        "date": {"type": "string"}, "day_summary": {"type": "string"},
        "highlights": {"type": "array"}, "architecture_decisions": {"type": "array"},
        "key_insights": {"type": "array"}, "tags": {"type": "array"},
        "themes": {"type": "array"}, "previous_feedback": {"type": "object"},
        "iteration": {"type": "integer"},
    }, "required": ["date", "day_summary", "highlights", "key_insights"],
}

OUTPUT_SCHEMA = {
    "type": "object", "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "mermaid": {"type": "string"},
    },
    "required": ["title", "content", "summary", "tags"],
}


class WriteAgent(BaseAgent):
    """Outputs a complete Markdown article. Templates handle platform formatting."""

    agent_name = "write"
    output_schema = OUTPUT_SCHEMA
    input_schema = INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        iteration = input_data.get("iteration", 1)
        fb = input_data.get("previous_feedback")
        feedback_section = ""
        if fb and iteration > 1:
            feedback_section = f"\n修订轮次 {iteration}。反馈：{fb.get('feedback', [])}\n"
        exp = input_data.get("experience_context", "")

        return f"""你是资深 Agent 架构师，根据当天技术工作输出一篇完整的 Markdown 技术文章。

日期：{date}
{feedback_section}
{exp}

## 输出字段

- title: 30字内，有数字/冲突/结果/技术名词
- summary: 2-3句总结
- tags: 3-5个小写英文标签
- content: **完整的 Markdown 文章**（见下文结构）
- mermaid: Mermaid图源码（graph TD/sequenceDiagram/flowchart），不能为空

## content 字段写作规范

content 是完整 Markdown，包含以下章节。**不要用结构化字段——全写进 Markdown 正文里。**

### 标题
正文第一行是 H1：`# 你的标题`（和 title 字段一致）

### 1. 背景与问题
写 2-3 段，描述今天遇到的具体技术挑战。为什么难？做错了会怎样？

### 2. 根因分析
每层追问"为什么"。用 `### 根因N：标题` 分节。

### 3. 方案
每段方案用 H3 标题分节，包含 Before/After 代码段和解释。
代码段用反引号包裹并标注语言。

### 4. 架构决策
用 Markdown 表格（| 列名 | 列名 | ），至少 2 行对比。

### 5. 生产考量
2-4条要点，每条用 `**标题**：内容` 格式。

### 6. 关键收获
3-5条，用 Markdown 列表 `- **标题**：内容（含数字或 trade-off）`

## 代码块格式

规则：
- 反引号开合必须成对出现
- 反引号后必须紧跟语言标签（python/java/bash/mermaid）
- 说明文字放代码块外面
- 代码里不能出现 {{image_url}} {{any_url}} 等花括号占位符

【重要】输出前自检：全文搜索是否包含单独一行的三个反引号。如果有，说明你输出了空代码块，删除它。

## 写作口吻
架构师视角，具体到数字，全文中文+技术术语英文。

## 隐私
禁止：API Key/密码/连接串/内网 IP/私钥。

返回纯 JSON，无任何其他内容。"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Minimal validation. No more _parse_* functions."""
        import re as _re

        for key in ["title", "content", "summary"]:
            if key not in output or not output.get(key, "").strip():
                ctx.error = f"Missing required field: {key}"
                raise ValueError(f"Article missing '{key}'")

        output.setdefault("mermaid", "")
        output.setdefault("tags", [])

        # Cleanup: remove empty ``` fences, replace placeholders, strip HTML
        content = output.get("content", "")
        content = _re.sub(r'^```\s*$', '', content, flags=_re.MULTILINE)
        content = _re.sub(r'\{([^}]+)\}', r'\1', content)
        content = _re.sub(r'<[a-zA-Z/][^>]*>', '', content)
        output["content"] = content

        return output
