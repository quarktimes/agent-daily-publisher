"""
Interview Agent — AI interview question generator.

Takes daily development work and generates realistic AI interview questions
with model answers. Each question is grounded in actual problems solved
today, not generic interview prep.

This turns passive daily work into active interview preparation —
every day you code is also a day you prepare for your next role.
"""

from datetime import datetime
from typing import Any

from core.agent import BaseAgent, AgentContext

INTERVIEW_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "day_summary": {"type": "string"},
        "highlights": {"type": "array"},
        "architecture_decisions": {"type": "array"},
        "key_insights": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["date", "day_summary", "highlights", "key_insights"],
}

INTERVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "summary": {"type": "string"},
        "question_count": {"type": "integer"},
        "difficulty_levels": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["title", "content", "question_count"],
}


class InterviewAgent(BaseAgent):
    """
    Generates AI interview questions based on daily work.

    Agent Pattern: Structured Generation + Role-Play
      - Takes real development activity
      - Frames it as interview scenarios
      - Provides model answers showing senior-level thinking
    """

    agent_name = "interview"
    output_schema = INTERVIEW_OUTPUT_SCHEMA
    input_schema = INTERVIEW_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        highlights = input_data.get("highlights", [])
        return f"""你是一位**资深 Agent 架构师**，正在为求职高级 AI 岗位的候选人出面试题。
题目必须基于 {date} 的真实技术工作，不能出通用题。

---

## 质量要求

每道题必须达到以下标准：

| 维度 | 合格标准 | 不合格表现 |
|------|---------|-----------|
| **真实性** | 题目来自今天实际解决的技术问题 | 泛泛的 "什么是 X" 题 |
| **深度** | 涉及架构权衡、生产环境考量、具体指标 | 只问概念不落地 |
| **代码** | 至少一段真实代码或伪代码 | 没有代码 |
| **实战性** | 包含踩坑经验、错误恢复、反面模式 | 只讲理想方案 |
| **面试信号** | 指出面试官会关注什么、常见错误 | 只给答案不给评判标准 |

## 出题范围

从今天实际工作中提炼，映射到这些领域（选最相关的 2-3 个）：

1. **Tool Calling** — Function Calling 设计、并行调用、错误恢复
2. **MCP 协议** — 工具发现、资源暴露、安全模型
3. **Agent 架构** — ReAct、Plan-Execute、Supervisor、多 Agent 编排
4. **LangChain4j** — Java 集成、AI Services、Tool Specs
5. **PgVector / RAG** — 向量检索、混合搜索、分块策略
6. **Prompt 工程** — System Prompt、CoT、Structured Output
7. **生产化 AI** — 成本控制、延迟、评估、可观测性
8. **Agentic Coding** — AI 辅助开发、工具使用、自修复
9. **AI 系统设计** — 架构取舍、扩展性、可靠性
10. **失败模式分析** — 幻觉、工具失效、边界情况

## 每道题的格式（严格按此结构）

\`\`\`markdown
## 🤖 Q1: [中文标题，体现技术深度]

**难度:** Senior / Staff
**领域:** Tool Calling / Agent 架构 / RAG 优化 / 生产化 AI
**场景:** [基于今日实际工作的场景描述，20-50 字]

**题目:**
[针对真实场景的开放性问题，必须包含具体的技术约束和冲突点]
好的题目示例：
  ❌ "如何设计一个 Agent？"
  ✅ "在 ReAct 循环中，如果某次 Tool Call 超时但其他调用成功，如何让 LLM 基于部分结果继续推理而不崩溃？具体如何设计超时和降级策略？"

**答案要点:**
[300-500 字，包含：]
1. 核心思路（一句话说清楚）
2. 具体方案（含代码示例）
3. 权衡分析（选了 A 放弃了 B 的理由）
4. 反面教训（常见错误、踩坑经验）
5. 指标衡量（怎么判断做得好不好）

**面试官会关注什么:**
- [候选人是否提到 X]
- [常见误区是什么]
- [可以追问的问题]
\`\`\`

## 语言要求

- 全部用**中文**写（包括标题、题目、答案）
- 技术术语用英文（如 ReAct、Tool Calling、MCP），不要强行翻译
- 代码注释用英文

## 输出要求

生成 3-5 道题，返回 JSON：
  - title: "AI 面试题日报 | YYYY-MM-DD"
  - content: 完整 Markdown，包含所有题目
  - summary: "基于今日工作生成 N 道 AI 面试题"
  - question_count: 题目数量
  - difficulty_levels: ["Senior", "Staff", ...]
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        content = output.get("content", "")
        if len(content.strip()) < 200:
            ctx.error = f"Generated interview content too short ({len(content)} chars)"
            raise ValueError(f"Interview content is only {len(content)} characters")

        if not output.get("title"):
            output["title"] = f"AI 面试题日报 | {ctx.input.get('date', datetime.now().strftime('%Y-%m-%d'))}"

        return output
