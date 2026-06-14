"""
Content Polishing Agent — Elevates article from "correct" to "compelling".

Unlike the Judge (which scores), this agent actively REWRITES:
  - Opening hook: turns bland intros into attention-grabbing leads
  - Paragraph flow: fixes choppy transitions, adds connector sentences
  - Title punch: makes titles sharper, more clickable
  - Code explanations: adds "why this works" context around code blocks
  - Closing: turns weak endings into memorable takeaways

The Polisher receives rendered Markdown, improves the writing quality,
and returns polished Markdown. It does NOT change technical content.
"""

from typing import Any

from core.agent import BaseAgent, AgentContext

POLISH_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "content"],
}

POLISH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "changes_made": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "content"],
}


class PolisherAgent(BaseAgent):
    """
    Enhances article writing quality without changing technical substance.

    Agent Pattern: Rewriting & Enhancement
      - Fixes voice/tone issues that structural tools can't catch
      - Adds narrative flow and engagement hooks
      - Preserves all code, diagrams, and technical claims exactly as-is
    """

    agent_name = "polisher"
    output_schema = POLISH_OUTPUT_SCHEMA
    input_schema = POLISH_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        title = input_data.get("title", "")
        return f"""你是资深技术编辑，负责将一篇技术文章从"正确但有距离感"打磨成"引人入胜的好文章"。

原文标题：{title}

## 你的任务

改写这篇文章，提升可读性和吸引力。但**严格禁止**改动以下内容：
- ❌ 不要改代码块（```...``` 内的全部保留原样）
- ❌ 不要改 Mermaid 图表
- ❌ 不要改技术声明和数据（如 "P99 降到 420ms"）
- ❌ 不要改架构决策表（ADR 表格）
- ✅ 可以改：标题、开头段落、段落过渡句、结尾、小标题、表述方式

## 改写重点

### 1. 标题优化
- 如果原文标题是 "技术日报 | 日期" 这种格式，彻底重写
- 加入数字、冲突、结果感："3 个正则救了崩溃的 Markdown 渲染"
- 30 字以内，中文

### 2. 开头重写
- 不要 "今天做了..." "最近在开发..." 这种流水账开头
- 用 2-3 句制造悬念或共鸣：
  ✅ "LLM 写代码很厉害，但你让它好好写个 Markdown？对不起，不行。"
  ✅ "我们的文档渲染系统又炸了。已经是这个月第三次。"
  ❌ "今天我在开发 Agent Daily Publisher 系统时..."

### 3. 段落过渡
- 每节之间加 1 句过渡："这个问题表面看是格式，根子却在..." / "既然 Prompt 不行，那只能..."
- 避免生硬跳转

### 4. 代码前后加一句话
- 代码块前："核心逻辑就这 5 行："
- 代码块后："就这 5 行，把渲染错误率从 15% 压到了 0。"
- 帮助读者快速理解代码价值

### 5. 结尾强化
- 不要 "以上就是今天的..." 或 "希望大家喜欢"
- 用一句话总结模式层面的洞察 + 行动号召
- ✅ "下次你的文档渲染崩了，别调 Prompt 了，先写个后处理管道吧。"

## 格式要求
- 保留原文所有 ``` 代码块完整不变
- 保留原文所有 Mermaid 图表完整不变
- 返回 JSON：{{"title": "优化后的标题", "content": "优化后的完整 Markdown", "changes_made": ["修改了...", "重写了..."]}}

返回纯 JSON，无任何其他内容。"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        if len(output.get("content", "")) < 100:
            # Polishing failed — return original unchanged
            output["content"] = ctx.input.get("content", "")
            output["title"] = ctx.input.get("title", output.get("title", ""))
            output["changes_made"] = ["(no changes — polishing skipped due to short output)"]
        return output
