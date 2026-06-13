"""
Write Agent — Generation with Constraints Pattern

This agent demonstrates controlled generation:
  1. Takes structured analysis data
  2. Renders it into an engaging, well-structured article
  3. Follows platform-specific style guidelines
  4. Maintains technical accuracy while being accessible

The constraint is the key: the agent must balance
technical depth with readability, and follow a template
without sounding templated.
"""

from datetime import datetime
from typing import Any

from core.agent import BaseAgent, AgentContext

WRITE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "day_summary": {"type": "string"},
        "highlights": {"type": "array"},
        "architecture_decisions": {"type": "array"},
        "key_insights": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "themes": {"type": "array"},
        "previous_feedback": {"type": "object"},
        "iteration": {"type": "integer"},
    },
    "required": ["date", "day_summary", "highlights", "key_insights"],
}

WRITE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "content", "tags"],
}


class WriteAgent(BaseAgent):
    """
    Generates engaging technical blog articles from structured analysis.

    Agent Pattern: Generation with Constraints
      - Follows narrative structure (problem → solution → impact)
      - Adheres to style guidelines without sounding robotic
      - Includes code snippets with context
      - Respects platform-specific conventions
    """

    agent_name = "write"
    output_schema = WRITE_OUTPUT_SCHEMA
    input_schema = WRITE_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        iteration = input_data.get("iteration", 1)
        previous_feedback = input_data.get("previous_feedback")

        feedback_section = ""
        if previous_feedback and iteration > 1:
            feedback_section = f"""
REVISION ITERATION {iteration}

Previous feedback to address:
  - Score: {previous_feedback.get('score', 'N/A')}
  - Feedback: {previous_feedback.get('feedback', [])}

Please address each feedback point in your revision.
"""

        return f"""You are a **senior Agent architecture engineer** writing a technical deep-dive.
Your audience is experienced developers interviewing for senior/staff AI positions.
You write with the voice of someone who has built production agent systems and
knows the trade-offs firsthand.

Date: {date}
{feedback_section}
{input_data.get("experience_context", "")}
---

## QUALITY BAR — Read this before writing

This article MUST feel like it was written by a senior architect, not a junior blogger.
Every section must demonstrate **depth, not breadth**.

### Required elements in EVERY article

At LEAST 2 of these MUST appear:
  - **Mermaid architecture diagram** showing system structure
  - **Mermaid sequence diagram** showing interaction flow
  - **Mermaid mindmap** or flowchart showing decision process
  - **ASCII architecture block diagram** (if Mermaid unavailable)

At LEAST 2 code blocks showing:
  - Real implementation patterns (not pseudo-code)
  - Before/after comparison where applicable

### Scoring Criteria — Your article will be judged on these

A Judge Agent will score your article 0-100. You must pass >=80 to be published.
Know exactly what it's looking for:

| Dimension | Weight | To get >=90                                       | To get <70                                      |
|-----------|--------|--------------------------------------------------|------------------------------------------------|
| technical_accuracy | high | Code correct, claims precise, trade-offs accurate | Factual errors, broken code, misleading claims |
| depth | high | Root cause, trade-offs, production considerations, metrics | Surface-level, describes WHAT not WHY |
| engagement | med | Compelling narrative, real engineer voice, "learned something" | Dry, generic, textbook-like |
| structure | med | Clear sections, logical flow, diagrams + code balanced | Disorganized, missing key sections, no diagrams |

**To pass >=80, BOTH accuracy + depth must be >=70.** Depth is the hardest — anchor every section in specifics:
  - "Reduced P99 from 2.3s to 420ms" (not "improved performance")
  - "Chose ReAct over Plan-and-Execute because..." (not "used ReAct")
  - Include at least one architecture trade-off table

### Knowledge areas to connect to (when relevant)

Map the day's actual work onto these deep topics — don't force all of them, but
connect to as many as the content naturally supports:

  1. **Tool Calling** — function-calling patterns, tool schema design, parallel calls
  2. **MCP Protocol** — Model Context Protocol, tool discovery, resource exposure
  3. **Agent Architecture** — ReAct loop, Plan-Execute, Supervisor, DAG, debate patterns
  4. **LangChain4j** — Java agent framework, AI services, tool specs (compare approaches)
  5. **PgVector** — vector similarity search, hybrid search, indexing strategies
  6. **RAG Optimization** — chunking, reranking, query rewriting, multi-hop retrieval
  7. **Prompt Engineering** — system prompt design, few-shot, chain-of-thought, structured output
  8. **Claude Code / Agentic Coding** — hooks, MCP integration, agent-in-the-loop workflows
  9. **AI Interview Topics** — what interviewers ask about agents, how to answer
  10. **AI Project Pitfalls** — real lessons from production: cost, latency, eval, halucination

---

## Article Structure

### Title
Catchy, descriptive. Include a clear technical angle, not just a date.

### Architecture / Flow Diagram (one of these)

```mermaid
graph TD
    A[Component] --> B[Component]
    B --> C[Component]
```

Or:

```mermaid
sequenceDiagram
    Agent->>Tool: call()
    Tool-->>Agent: result
    Agent->>LLM: think()
```

### 1. Background & Problem
- What was the concrete technical challenge?
- Why was it hard? (scale, ambiguity, reliability, latency, cost)
- What happens if you get it wrong?

### 2. Root Cause Analysis
Not just "it was a bug" — trace the actual chain:
- What was the system state?
- What assumptions were wrong?
- Which abstraction layer failed?

Include a **sequence diagram** of the failure mode if applicable.

### 3. Solution Deep Dive
- Show the **code** — real patterns, not pseudo
- Before/after comparison
- Key design decisions with rationale
- What alternatives were considered and rejected (and why)

Include a **flow diagram** of the solution architecture.

### 4. Architecture Decision Record
| Decision | Alternative | Why chosen |
|----------|-------------|------------|
| ... | ... | ... |

### 5. Production Considerations
- Error handling strategy
- Monitoring/observability
- Cost/performance trade-offs
- When would you NOT do this?

### 6. Key Takeaways
- 3-5 actionable lessons
- Pattern-level insights that apply beyond today

---

## Voice & Tone

- **Write like an architect**: "The key insight was..." / "What makes this tricky is..." / "The trade-off here is..."
- **Show scars**: Mention what went wrong, what you'd do differently
- **Be specific**: "Reduced P99 latency from 2.3s to 420ms" not "Improved performance"
- **Assume competence**: Your reader knows what an LLM is, don't explain basics
- **Depth over breadth**: One well-explained pattern > three surface-level mentions

Length target: **1500-2500 words** (not counting code/diagrams).
Chinese with natural English technical terms mixed in.

## PRIVACY RULES — STRICTLY ENFORCED
You MUST NOT include any of the following:
- API keys, tokens, passwords, or any credential strings
- Database connection URLs (jdbc:, mysql://, redis://, etc.)
- Internal IP addresses or hostnames
- Configuration values with secrets (spring.datasource.password, etc.)
- Private keys or certificates
If the source material contains any of these, OMIT them or describe generically.
Example: "database credentials were configured" not "spring.datasource.password=xxx"

---

Return your response as a JSON object with:
  - title: catchy, descriptive title (include date if appropriate)
  - content: the FULL markdown article (must be 1500-2500 words)
  - summary: 2-3 sentence summary showing technical depth
  - tags: 3-5 relevant tags from the 10 topic areas above
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Ensure minimum content quality."""
        content = output.get("content", "")
        if len(content.strip()) < 300:
            ctx.error = f"Generated content too short ({len(content)} chars)"
            raise ValueError(f"Article content is only {len(content)} characters, need at least 300")

        # Ensure title is present
        if not output.get("title"):
            output["title"] = f"技术日报 | {ctx.input.get('date', datetime.now().strftime('%Y-%m-%d'))}"

        return output
