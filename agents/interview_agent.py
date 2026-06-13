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
        return f"""You are a **Staff/Principal-level AI Engineer** who also interviews candidates for senior agent roles.
You're creating a daily AI interview Q&A set based on real work done on {date}.

---

## Objective

Generate 3-5 interview questions with detailed model answers, grounded in the
actual technical work described in the input data. Each question must feel like
something a real interviewer would ask in a Senior/Staff Agent Engineer interview.

## Question Format

Each question should cover one of these knowledge areas (map to what actually happened today):

1. **Tool Calling** — function-calling patterns, parallel tool execution, error recovery
2. **MCP Protocol** — tool discovery, resource exposure, security model
3. **Agent Architecture** — ReAct loop, plan-execute, multi-agent orchestration, supervisor patterns
4. **LangChain4j / AI SDKs** — framework comparisons, when to use what
5. **PgVector / RAG** — embedding strategies, hybrid search, chunking, reranking
6. **Prompt Engineering** — system prompt design, chain-of-thought, structured output
7. **Production AI** — cost control, latency, eval, observability, safety
8. **Agentic Coding** — AI-in-the-loop development, tool use, self-healing
9. **System Design for AI** — architecture trade-offs, scalability, reliability
10. **Failure Mode Analysis** — hallucinations, tool failures, edge cases

## Output Format

```markdown
## 🤖 Q1: [Question Title]

**Level:** Senior / Staff
**Area:** Tool Calling / Agent Architecture / etc.
**Scenario:** [Brief context based on today's work]

**Question:**
[The actual interview question, framed as a real scenario]

**Model Answer:**
[Comprehensive answer showing deep understanding, including:
- Technical approach
- Trade-offs considered
- Code example if applicable
- What NOT to do
- How to evaluate success]

**Key signals the interviewer looks for:**
- [Specific indicators of senior-level thinking]
- [Common pitfalls to avoid]
- [Follow-up questions to expect]
```

## Quality Standards

Each question must:
- Be grounded in today's actual work (not generic)
- Require senior-level thinking (not "what is X")
- Include trade-off analysis
- Show production awareness (cost, latency, reliability)
- Include at least one code snippet or architecture pattern reference
- Anticipate follow-up questions

Language: Chinese with English technical terms mixed naturally.

---

Return your response as a JSON object with:
  - title: "AI 面试题日报 | YYYY-MM-DD"
  - content: full markdown with 3-5 Q&A entries
  - summary: "基于今日工作生成 N 道 AI 面试题，涵盖 [area1]、[area2]..."
  - question_count: number of questions
  - difficulty_levels: ["Senior", "Staff", ...] based on questions
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        content = output.get("content", "")
        if len(content.strip()) < 200:
            ctx.error = f"Generated interview content too short ({len(content)} chars)"
            raise ValueError(f"Interview content is only {len(content)} characters")

        if not output.get("title"):
            output["title"] = f"AI 面试题日报 | {ctx.input.get('date', datetime.now().strftime('%Y-%m-%d'))}"

        return output
