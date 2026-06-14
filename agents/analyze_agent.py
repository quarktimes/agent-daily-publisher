"""
Analyze Agent — Chain-of-Thought Pattern

This agent demonstrates the Chain-of-Thought (CoT) pattern:
  1. Takes raw session data (multiple sessions, varied topics)
  2. Reasons step-by-step through the day's work
  3. Identifies patterns: what problems were solved, what decisions made
  4. Extracts deep insights, not surface-level summaries

The CoT pattern enables the agent to:
  - Separate signal from noise across many sessions
  - Connect related work that happened in separate sessions
  - Infer root causes from conversations about symptoms
"""

from typing import Any

from core.agent import BaseAgent, AgentContext

ANALYZE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "sessions": {"type": "array"},
        "total_prompts": {"type": "integer"},
        "projects": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["date", "sessions"],
}

ANALYZE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "day_summary": {"type": "string"},
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "description": {"type": "string"},
                    "related_projects": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["problem", "solution", "decision", "insight", "achievement"]},
                    "title": {"type": "string"},
                    "context": {"type": "string"},
                    "root_cause": {"type": "string"},
                    "solution": {"type": "string"},
                    "impact": {"type": "string"},
                    "code_snippet": {"type": "string"},
                },
                "required": ["type", "title"],
            },
        },
        "architecture_decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string"},
                    "rationale": {"type": "string"},
                    "alternatives": {"type": "string"},
                    "tradeoffs": {"type": "string"},
                },
            },
        },
        "key_insights": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["date", "day_summary", "highlights", "key_insights"],
}


class AnalyzeAgent(BaseAgent):
    """
    Analyzes raw session data to extract structured technical insights.

    Agent Pattern: Chain-of-Thought
      - Reasons step-by-step through session data
      - Identifies cross-session patterns
      - Extracts root causes, not just symptoms
      - Categorizes work into meaningful themes
    """

    agent_name = "analyze"
    output_schema = ANALYZE_OUTPUT_SCHEMA
    input_schema = ANALYZE_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        session_count = len(input_data.get("sessions", []))
        return f"""你是 Analyze Agent，负责从 Claude Code 的会话数据中提取结构化的技术洞察。

分析日期：{date}
捕获会话数：{session_count}

按以下步骤逐步推理：

第1步 — 扫描：通读所有会话，今天做了哪些大类工作？
第2步 — 识别问题：对每个技术问题，提取：
  - 实际问题是什么？（不是表面现象）
  - 根因是什么？
  - 如何解决的？
第3步 — 提取决策：做了什么架构或设计决策？为什么？
第4步 — 发现关联：跨会话之间有没有共同的主题或规律？
第5步 — 量化影响：产生了什么效果？（bug修复数、功能完成数、性能提升数）

输出规则：
  - 每个 highlight 必须有明确的 type：problem | solution | decision | insight | achievement
  - 对于 problem 类型，必须包含 root_cause —— 如果不明显就推断
  - 架构决策必须包含 rationale 和 tradeoffs
  - key_insights 应该是跨今天的通用经验教训
  - Tags 用大类（如 "backend", "frontend", "devops", "AI", "bug-fix"）

质量标准：
  - 具体："修复了 UserService.findByOrg() 中的 N+1 查询" 而非 "修复了性能问题"
  - 准确：只提取会话数据支持的内容，不做无依据推断
  - 有洞察：尽可能发现跨会话的关联点
"""
