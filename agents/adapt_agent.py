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

        return f"""你是 Adapt Agent，将通用中文技术文章适配到不同平台。

目标平台：{platform_desc}

## 核心原则
1. **技术正确性不变** — 不管怎么适配，代码和技术声明一个字不能错
2. **一个平台一个版本** — 不是翻译，是改写，每个平台读起来像"原生于那个平台"
3. **不降智** — 即使简化表达，保留核心洞察和技术深度

## 各平台适配速查

### 掘金
- 语言：中文 + 英文术语
- 风格：技术博客体，像同事写的内部 Wiki
- 代码：保留全部代码块，技术细节不删
- 标签：3-5 个中文标签（如 "Agent架构", "RAG优化"）
- 篇幅：1000-2000 字
- 标题风格：直击技术要点，不用问句
  - ✅ "Agent 发布流水线的三级容错设计"
  - ❌ "你知道 Agent 发布失败该怎么办吗？"

### Dev.to
- 语言：英文（完整翻译，不是机翻）
- 风格：Practical tutorial / Lessons learned
- 代码：保留，注释翻译成英文
- 标签：3-4 个小写英文（如 "agents", "rag", "tutorial"）
- 篇幅：800-1500 字
- 标题风格：直接、有悬念
  - ✅ "I Built a Publishing Pipeline That Survives API Failures"
  - ❌ "Multi-Platform Article Publishing System"

### 微信公众号
- 语言：中文
- 风格：对话感，像在给朋友讲今天做的事
- 代码：精简到 1-2 个关键片段，大段代码改成文字描述
- 标题：吸引点击但不能标题党，控制在 20 字左右
- 段落：每段不超过 3 行，用短句
- 篇幅：800-1200 字
- ❌ 禁止：大段代码、长段落、多级嵌套标题

## 通用规则
- 保留所有技术声明和代码正确性
- 标题按平台风格改，不要机械翻译
- 每个版本独立完整，可以单独发布
- 输出中不要包含这些指令文本
- 返回 JSON：{{"versions": [{{"platform": "juejin/devto/wechat_mp", "title": "...", "content": "...", "tags": [...], "language": "zh/en"}}]}}
"""
