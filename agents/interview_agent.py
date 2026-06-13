"""
Interview Agent — AI interview question generator.

Takes daily development work and generates realistic AI interview questions
with model answers. Each question is grounded in actual problems solved
today, not generic interview prep.
"""

from datetime import datetime
from typing import Any

from core.agent import BaseAgent, AgentContext

_INPUT_SCHEMA = {
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

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "summary": {"type": "string"},
        "question_count": {"type": "integer"},
        "difficulty_levels": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "content", "question_count"],
}

# Prompt template (avoid f-string to prevent curly-brace escaping issues with code blocks)
_PROMPT_HEAD = """你是一位资深Agent架构师，正在为求职高级AI岗位的候选人出面试题。
题目必须基于 %s 的真实技术工作，不能出通用题。

---

## 质量要求

每道题必须达到以下标准：

| 维度 | 合格标准 | 不合格表现 |
|------|---------|-----------|
| 真实性 | 题目来自今天实际解决的技术问题 | 泛泛的概念题 |
| 深度 | 涉及架构权衡、生产环境考量、具体指标 | 只问概念不落地 |
| 代码 | 至少一段真实代码或伪代码，格式整洁 | 没有代码或代码混乱 |
| 实战性 | 包含踩坑经验、错误恢复、反面模式 | 只讲理想方案 |
| 信号 | 指出面试官会关注什么、常见错误 | 只给答案不给标准 |

## 代码格式要求

Java/Python代码必须格式整洁：
```
// 正确：缩进统一、空行合理
public interface Extractor {
    @UserMessage("Extract data")
    Data extract(String text);
}
```
禁止输出混乱缩进、缺少关键字的代码。

## 出题范围

从今天实际工作中提炼，选最相关的2-3个领域：

1. Tool Calling - Function Calling设计、并行调用、错误恢复
2. MCP协议 - 工具发现、资源暴露、安全模型
3. Agent架构 - ReAct、Plan-Execute、Supervisor、多Agent编排
4. LangChain4j - Java集成、AI Services、Tool Specs
5. PgVector/RAG - 向量检索、混合搜索、分块策略
6. Prompt工程 - System Prompt、CoT、Structured Output
7. 生产化AI - 成本控制、延迟、评估、可观测性
8. Agentic Coding - AI辅助开发、工具使用、自修复
9. AI系统设计 - 架构取舍、扩展性、可靠性
10. 失败模式分析 - 幻觉、工具失效、边界情况

## 每道题的格式

```
## Q1: [中文标题]

难度: Senior / Staff
领域: Tool Calling / Agent架构 / RAG优化
场景: [基于今日实际工作的场景描述]

题目:
[开放性问题，必须包含具体的技术约束和冲突点]

答案要点:
1. 核心思路
2. 具体方案（含代码）
3. 权衡分析
4. 反面教训
5. 衡量指标

面试官会关注什么:
- 候选人是否提到X
- 常见误区
- 可追问的问题
```

## 语言要求

全部用中文写，技术术语保持英文（ReAct、MCP、Tool Calling）。
代码注释用英文。
"""


class InterviewAgent(BaseAgent):
    """
    Generates AI interview questions based on daily work.
    """

    agent_name = "interview"
    output_schema = _OUTPUT_SCHEMA
    input_schema = _INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        return _PROMPT_HEAD % date

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        content = output.get("content", "")
        if len(content.strip()) < 200:
            ctx.error = f"Interview content too short ({len(content)} chars)"
            raise ValueError(f"Interview content is only {len(content)} characters")

        if not output.get("title"):
            output["title"] = "AI面试题日报 | %s" % ctx.input.get("date", datetime.now().strftime("%Y-%m-%d"))

        return output
