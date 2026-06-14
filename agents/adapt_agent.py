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

        return f"""你是 Adapt Agent，负责将同一篇文章适配到不同平台的风格。

目标平台：
{platform_desc}

为每个平台做以下适配：

1. **掘金** — 中文，开发者
   - 技术深度：高
   - 保留代码示例，增加技术细节
   - 中文 + 英文技术术语
   - 标签：3-5 个中文标签
   - 篇幅：1000-2000 字

2. **Dev.to** — 英文，全球开发者
   - 技术深度：中高
   - 全文英文翻译
   - 侧重实用、可操作的内容
   - 标签：最多 4 个，小写英文
   - 篇幅：800-1500 字

3. **Medium** — 英文，泛技术受众
   - 技术深度：中
   - 增加叙事弧线：问题 → 探索 → 方案 → 洞察
   - 少代码，多概念解释
   - 篇幅：600-1200 字

4. **知乎** — 中文，偏思辨
   - 技术深度：高
   - 侧重方法论和底层原理，代码少而精
   - 增加与替代方案的对比
   - 篇幅：1000-2000 字

5. **微信公众号** — 中文，移动端优先
   - 技术深度：中低
   - 简化代码，重概念
   - 短段落、多留白
   - 语气亲切、有互动感
   - 篇幅：800-1200 字

通用规则：
  - 保留所有技术声明和代码准确性
  - 根据平台风格调整标题
  - 每个平台返回一个版本
  - 每个版本必须是完整可发布的文章
  - 输出中不要包含这些指令文本
"""
