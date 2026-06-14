"""
Claude Code Usage Analysis — Meta-cognition for developer-AI collaboration.

Produces a daily coach report with score, patterns, and actionable suggestions
including new Skills to create, CLAUDE.md updates, and expected savings.
"""

from datetime import datetime
from typing import Any

from core.agent import BaseAgent, AgentContext

ANALYSIS_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "sessions": {"type": "array"},
        "day_summary": {"type": "string"},
        "highlights": {"type": "array"},
    },
}

ANALYSIS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "positive_patterns": {"type": "array", "items": {"type": "string"}},
        "negative_patterns": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
        "suggested_skills": {"type": "array", "items": {"type": "string"}},
        "suggested_claude_updates": {"type": "array", "items": {"type": "string"}},
        "token_savings_pct": {"type": "integer"},
        "round_savings_pct": {"type": "integer"},
    },
    "required": ["title", "content", "score"],
}


class UsageAnalysisAgent(BaseAgent):
    """Analyzes Claude Code prompting patterns and produces a coach report."""

    agent_name = "usage_analysis"
    output_schema = ANALYSIS_OUTPUT_SCHEMA
    input_schema = ANALYSIS_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        sessions = input_data.get("sessions", [])
        session_count = len(sessions)
        prompt_count = sum(len(s.get("prompts", [])) for s in sessions)

        return f"""你是资深 AI 协作教练。分析今天 {date} 使用 Claude Code 的 {session_count} 个会话（{prompt_count} 条提问），输出结构化教练报告。

## 报告模板 — 严格按此格式输出

```
## 今日评分

总体评分：{0-100}

## 做得好的地方
- 每条 20 字以内，具体到某条提问
- 引用用户的真实提问作为例证

## 可以改进的地方
- 指出具体的 prompt 写法问题
- "你在提问X时没有说明Y，导致Claude走了Z步"
- 每条附改进后的 prompt 示例

## 建议新增 Skill
如果今天有 2 次以上做同一类事（如建 Agent、查数据库），就应该创建一个 Skill 来固化。
列出 1-3 个 /skill 名和说明：
- /create-agent: 一键创建 Agent 骨架（prompt + schema + test）
- /...

## 建议更新 CLAUDE.md
根据今天的会话，项目级的 CLAUDE.md 缺少什么信息？
例：
- MCP Server 配置说明
- Agent 命名规范
- 测试命令

## 节省机会（量化分析）

根据今天反复纠正型的对话轮次占比，预计可减少：
- Token：X%(不必要的重试和纠正)
- 对话轮数：Y%(因初始 prompt 信息不足导致的返工)
```

## 评分标准（0-100）

| 扣分项 | 扣分 |
|-------|------|
| 模糊提问（"给我优化一下"类） | -5/次 |
| 缺少技术栈说明导致 Claude 猜 | -5/次 |
| 同样的事做 2 次以上无 Skill | -3/次 |
| 反复纠正同一问题（>3 轮） | -5/次 |
| 没有让 Claude 读项目文件直接问 | -3/次 |
| 拿到方案不追问 trade-off | -2/次 |

| 加分项 | 加分 |
|-------|------|
| 提问时给了具体指标 | +5/次 |
| 主动要求解释 trade-off | +5/次 |
| 用 /skill 或高级功能 | +5/次 |
| 一次性给出完整上下文 | +5/次 |

## 输出要求

必须包含实际案例引用（用户是怎么问的，Claude 是怎么回答的）。
建议要具体可执行，不说套话。

格式：JSON
  - title: "Claude Code 使用复盘 | YYYY-MM-DD"
  - content: 完整 Markdown 报告
  - score: 0-100
  - positive_patterns: 字符串数组
  - negative_patterns: 字符串数组
  - suggestions: 字符串数组
  - suggested_skills: 字符串数组（每个含 /skill 名称和说明）
  - suggested_claude_updates: 字符串数组
  - token_savings_pct: 整数百分比
  - round_savings_pct: 整数百分比
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        for field in ["positive_patterns", "negative_patterns", "suggestions", "suggested_skills", "suggested_claude_updates"]:
            if field not in output or not output[field]:
                output[field] = []
        content = output.get("content", "")
        if len(content.strip()) < 100:
            output["content"] = f"# Claude Code 使用复盘 | {ctx.input.get('date', '')}\n\n> 会话数据不足以生成完整分析。\n"
        return output
