# Agent Daily Publisher — Architecture Document

> *This document is the primary artifact for evaluating this project. It captures the design rationale, trade-off analysis, and architectural decisions that distinguish a production agent system from a script collection.*

---

## Table of Contents

1. [System Philosophy](#1-system-philosophy)
2. [Agent Design Principles](#2-agent-design-principles)
3. [The Six Agents](#3-the-six-agents)
4. [Data Flow & Communication](#4-data-flow--communication)
5. [Error Recovery Strategy](#5-error-recovery-strategy)
6. [Observability](#6-observability)
7. [Key Design Decisions](#7-key-design-decisions)
8. [Production Considerations](#8-production-considerations)
9. [Extending the System](#9-extending-the-system)

---

## 1. System Philosophy

### 1.1 What This System Is

A **multi-agent pipeline** that transforms raw development activity into published technical content. Each stage of the pipeline is an independent agent with decision-making authority, not a hard-coded function.

### 1.2 What This System Is Not

- ❌ **Not a LangChain/CrewAI application** — We build our own agent framework from first principles to demonstrate deep understanding
- ❌ **Not a monolith** — Agents are independently deployable and testable
- ❌ **Not a script collection** — Agents make decisions; scripts follow instructions

### 1.3 Why This Architecture

The pipeline pattern was chosen over alternatives:

| Approach | Verdict | Why |
|----------|---------|-----|
| **Single Agent** | ❌ Rejected | Too much context crammed into one prompt; prompt engineering nightmare |
| **Pipeline (chosen)** | ✅ Selected | Clear separation of concerns; each stage is independently testable and optimizable |
| **DAG / Mesh** | ❌ Rejected | Over-engineered for linear processing; adds complexity without benefit |

The pipeline is the right abstraction when:
- Input flows through distinct transformation stages
- Each stage has different success criteria
- Stages can be independently optimized or replaced

---

## 2. Agent Design Principles

### 2.1 Agents Are Not Functions

A function executes. An agent **decides**. The distinction:

| | Function | Agent (this system) |
|--|----------|-------------------|
| **Control flow** | Hard-coded | LLM decides tool order |
| **Error handling** | Caller handles | Agent retries, falls back, or escalates |
| **Output** | Raw value | Structured + validated against schema |
| **Context** | Parameters only | System prompt + tools + memory + session state |

### 2.2 The ReAct Loop

Every agent follows the ReAct (Reasoning + Acting) pattern:

```
1. Thought: "What data do I need and what tool can get it?"
2. Action: Call tool with specific parameters
3. Observation: Process tool output
4. Repeat until goal is met
5. Final: Return structured output
```

### 2.3 Structured Output Contracts

Agents communicate through **JSON Schema contracts**, not free text:

```
┌──────────┐     JSON Schema A     ┌──────────┐
│ Agent A  │ ───────────────────→  │ Agent B  │
│ (producer)│  (validated on read)  │(consumer)│
└──────────┘                       └──────────┘
```

This guarantees:
- **Type safety** — Agent B knows exactly what fields to expect
- **Validation** — Malformed output is caught at the boundary, not downstream
- **Evolution** — Schemas can version independently per agent

### 2.4 Tool Registry Pattern

Tools are **registered dynamically**, not hard-coded:

```python
# Instead of:
def run_agent(input):
    result1 = read_history(input)
    result2 = read_git(result1)
    return process(result2)

# We do:
registry = ToolRegistry()
registry.register("load_history", fn=read_history)
registry.register("get_git_log", fn=get_git_log)

agent = BaseAgent(tool_registry=registry)
agent.run(input_data)  # Agent decides tool order at runtime
```

This enables:
- Tools added without modifying agent code
- Runtime tool discovery ("what can I do?")
- Each tool carries self-describing metadata

---

## 3. The Six Agents

### 3.1 Capture Agent — Tool-Use Pattern

**Purpose**: Extract raw session data from Claude Code logs and git history.

**Key design decisions**:
- Reads `~/.claude/history.jsonl` for session metadata
- Uses git log for code change context
- Partial data is acceptable (graceful degradation)
- Deduplicates repeated entries (same query within 60s)

**What it demonstrates**:
- Dynamic tool discovery (log reader, git analyzer)
- Data aggregation from multiple sources
- Structured output with schema validation

**Input schema**:
```json
{"date": "2026-06-09"}
```

**Output schema** (simplified):
```json
{
  "date": "2026-06-09",
  "sessions": [{"session_id": "...", "project": "...", "prompts": [...]}],
  "total_prompts": 12,
  "projects": ["/project/a", "/project/b"]
}
```

### 3.2 Analyze Agent — Chain-of-Thought Pattern

**Purpose**: Transform raw session data into structured technical insights.

**Key design decisions**:
- Multi-step reasoning: scan → identify → extract → connect
- Highlights include type classification (problem/solution/decision/insight/achievement)
- Cross-session pattern detection
- Root cause inference (not just surface summary)

**What it demonstrates**:
- Chain-of-Thought reasoning
- Information classification and abstraction
- Deep extraction (connecting related sessions)

**Output highlights**:
```json
{
  "type": "problem",
  "title": "N+1 query in UserService.findByOrg()",
  "root_cause": "Eager loading not configured for org-User relationship",
  "solution": "Added @EntityGraph to repository method",
  "impact": "Reduced query count from N+1 to 2"
}
```

### 3.3 Write Agent — Generation with Constraints Pattern

**Purpose**: Generate engaging technical articles from structured analysis.

**Key design decisions**:
- Follows narrative structure (context → problem → solution → impact)
- Adheres to style guide (specific, accurate, insightful)
- Platform-aware formatting (code blocks, link syntax, etc.)
- Length targets (800-1500 words)

**What it demonstrates**:
- Controlled generation within constraints
- Template adherence without sounding templated
- Code snippet accuracy preservation

### 3.4 Judge Agent — Self-Evaluation Pattern

**Purpose**: Evaluate article quality across multiple dimensions and decide pass/fail.

**Key design decisions**:
- Five evaluation dimensions (technical accuracy, clarity, engagement, structure, actionability)
- Score 0-100 per dimension
- Verdict: pass (≥70, no dimension <60) | revise | reject
- Actionable feedback for revision

**What it demonstrates**:
- Self-evaluation / Critic pattern
- Multi-dimensional quality scoring
- Feedback loop for improvement
- Configurable thresholds (pass threshold, max iterations)

**The revision loop**:
```
Write Agent → Judge Agent
                 │
          ┌──────┼──────┐
          │      │      │
        pass  revise  reject
          │      │      │
          │   ┌──┘      │
          │   │  (loop  │
          │   │   back) │
          ▼   ▼         ▼
      Publish  Write   Manual
               again  Review
```

### 3.5 Adapt Agent — Transformation Pattern

**Purpose**: Adapt articles for different platform audiences.

**Key design decisions**:
- Platform-specific tone and depth
- Language adaptation (Chinese vs English)
- Content restructuring per platform constraints
- Tag optimization per platform rules

**Platform adaptations**:

| Platform | Language | Technical Depth | Code Examples | Length |
|----------|----------|----------------|---------------|--------|
| 掘金 | zh | High | Full | 1000-2000 |
| Dev.to | en | Medium-High | Full | 800-1500 |
| Medium | en | Medium | Few | 600-1200 |
| 知乎 | zh | High | Few | 1000-2000 |
| 公众号 | zh | Low-Medium | Minimal | 800-1200 |

**What it demonstrates**:
- Content transformation and style transfer
- Multi-language generation
- Platform constraint handling (tag limits, length limits)

### 3.6 Publish Agent — Tool-Use + Error Recovery Pattern

**Purpose**: Publish articles to target platforms via their APIs.

**Key design decisions**:
- Each publisher is a registered tool
- Retry with exponential backoff (2s → 4s → 8s)
- Graceful degradation (one platform failure ≠ all fail)
- Dry-run mode for testing without publishing

**Error recovery matrix**:

| Error | Strategy |
|-------|----------|
| Rate limit (429) | Wait 30s, retry once |
| Auth failure (401/403) | Skip, don't retry |
| Server error (5xx) | Retry with backoff (3×) |
| Network timeout | Retry with backoff (3×) |
| Invalid article | Skip, log detailed error |

**What it demonstrates**:
- Production error recovery
- Partial failure handling
- Retry strategies with backoff
- Idempotent publish design

---

## 4. Data Flow & Communication

### 4.1 Pipeline Execution Flow

```
                    Input: {"date": "2026-06-09"}
                            │
                    ┌───────▼────────┐
                    │  Capture Agent │
                    └───────┬────────┘
                            │ Structured sessions JSON
                    ┌───────▼────────┐
                    │  Analyze Agent │
                    └───────┬────────┘
                            │ Structured analysis JSON
                    ┌───────▼────────┐
                    │  Write Agent   │◄──────────────────┐
                    └───────┬────────┘                   │
                            │ Article draft               │
                    ┌───────▼────────┐                   │
                    │  Judge Agent   │  (feedback loop)    │
                    └───────┬────────┘                   │
                            │ pass/revise                  │
                            │ (revise → go back) ─────────┘
                            │ (pass → continue)
                    ┌───────▼────────┐
                    │  Adapt Agent   │
                    └───────┬────────┘
                            │ Platform-specific versions
                    ┌───────▼────────┐
                    │  Publish Agent │
                    └───────┬────────┘
                            │ Published URLs
                    ┌───────▼────────┐
                    │    Results     │
                    └────────────────┘
```

### 4.2 Agent Communication Protocol

All inter-agent communication uses JSON Schema:

```python
# Producer (Analyze Agent)
output_schema = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "highlights": {"type": "array", ...},
        "architecture_decisions": {"type": "array", ...},
    },
    "required": ["date", "highlights"]
}
# → Agent produces output, validated before passing forward

# Consumer (Write Agent)
# → Receives already-validated data, guaranteed contract
```

### 4.3 Data Persistence

```
data/
├── sessions/YYYY-MM-DD.jsonl     # Raw captured turns (via hook)
├── articles/YYYY-MM-DD_*.md      # Generated article drafts
├── published/YYYY-MM-DD.json     # Publication records
├── traces/YYYY-MM-DD_*.jsonl     # Observability traces
└── memory/day_*.jsonl            # Agent memory (persistent context)
```

---

## 5. Error Recovery Strategy

### 5.1 Agent-Level Recovery

```
Agent.run(input)
  for attempt in 0..max_retries:
    try:
      output = llm_call(prompt)
      validated = schema_validator.validate(output)
      return validated
    except SchemaValidationError:
      prompt += f"\nFix: {validation_error}"
    except APIError:
      sleep(backoff(attempt))
  raise MaxRetriesExceeded
```

### 5.2 Pipeline-Level Recovery

```
PipelineOrchestrator.run(initial_input)
  for stage in stages:
    try:
      stage.agent.run(current_input)  # Agent handles its own retries
    except MaxRetriesExceeded:
      log_error(stage.name)
      continue_to_next_stage = True  # Pipeline continues
  return partial_results
```

### 5.3 Partial Failure Semantics

| Scenario | Behavior |
|----------|----------|
| Capture fails | Pipeline aborts (no data to process) |
| Analyze fails | Abort (no content to write) |
| Write fails | Abort (no article to publish) |
| Judge rejects after N iterations | Publish last version with warning |
| Adapt fails for one platform | Skip that platform, continue others |
| Publish fails for one platform | Skip that platform, continue others |

---

## 6. Observability

### 6.1 What We Track

Every agent operation produces a trace record:

```json
{
  "type": "agent_run",
  "agent": "capture",
  "run_id": "a1b2c3d4e5f6",
  "duration_seconds": 3.45,
  "retry_count": 0,
  "token_usage": {"input": 1500, "output": 800},
  "error": null
}
```

### 6.2 Trace Types

| Type | Records | Used For |
|------|---------|----------|
| `agent_run` | Per agent invocation | Performance, cost, error tracking |
| `tool_call` | Per tool invocation | Usage patterns, failure diagnosis |
| `pipeline_run` | Per pipeline execution | End-to-end metrics |
| Log lines | Per decision point | Understanding agent reasoning |

### 6.3 MCP Server

The MCP Server exposes pipeline state to external systems:

```python
# Query from Claude Code:
# "What articles were published today?"
tools = ["get_today_summary", "get_recent_sessions",
         "get_pipeline_status", "get_recent_articles"]
```

---

## 7. Key Design Decisions

### 7.1 Why Build Our Own Agent Framework (not LangChain/CrewAI)

| Factor | Custom Framework | LangChain / CrewAI |
|--------|-----------------|-------------------|
| **Expressiveness** | Full control over agent loop | Constrained by abstractions |
| **Transparency** | Every line is understood | Magic abstractions hide bugs |
| **Interview signal** | Proves deep understanding | Proves library familiarity |
| **Maintenance** | Minimal dependencies | Fast-moving target, breaking changes |
| **Weight** | ~600 lines total | Heavy dependency tree |

**Decision**: Custom framework. The goal is to demonstrate understanding, not tool proficiency.

### 7.2 Why Pipeline (not DAG or Mesh)

| Pattern | When To Use | Why Not Here |
|---------|-------------|-------------|
| **Pipeline** | Sequential transformation stages | ✅ Perfect fit — data flows linearly |
| **DAG** | Branching/joining data flows | ❌ Over-engineered — no branching needed |
| **Mesh** | Dynamic agent discovery | ❌ Premature — no need for runtime topology changes |

**Decision**: Pipeline is the simplest correct architecture. We don't add complexity without justification.

### 7.3 Why JSON Schema (not free text)

| Format | Pros | Cons |
|--------|------|------|
| Free text | Flexible | No contract enforcement, parsing errors |
| JSON Schema | Type-safe, self-documenting | Requires validation step |
| Protobuf | Efficient, strict | Over-engineered for this scale |

**Decision**: JSON Schema. The validation step is a small cost for guaranteed contract enforcement.

### 7.4 Why JSON Lines (not SQLite)

| Storage | When | Why |
|---------|------|-----|
| JSON Lines | Append-only logs, traces | ✅ Perfect — we only append, never update |
| SQLite | Relational data, queries | ❌ Over-engineered — no complex queries needed |
| Parquet | Large-scale analytics | ❌ Premature optimization |

**Decision**: JSON Lines. Simple, append-only, human-readable, trivially parseable.

---

## 8. Production Considerations

### 8.1 Cost Management

| Strategy | Implementation |
|----------|---------------|
| Token budget per agent | `max_tokens: 4096` per LLM call |
| Caching | Repeated prompts cache-hit on Anthropic API |
| Model tiering | Sonnet for agents (reasoning), Haiku for formatting (future) |
| Dry-run mode | Test pipeline without API costs |

### 8.2 Rate Limiting

```python
# Per-platform rate limiting in Publish Agent
backoff_strategy = {
    429: 30_000,   # Rate limited: wait 30s
    500: 2_000,    # Server error: wait 2s
    503: 5_000,    # Unavailable: wait 5s
}
retry_count = 0
while retry_count < 3:
    response = api_call()
    if response.status in backoff_strategy:
        sleep(backoff_strategy[response.status])
        retry_count += 1
    else:
        break
```

### 8.3 Scheduling

```bash
# Daily cron (6 PM)
0 18 * * * /path/to/scripts/daily-run.sh --publish

# Or via launchd for macOS persistence
# See scripts/daily-run.sh for details
```

### 8.4 Security

- API keys stored in environment variables, not code
- Platform configs support `${ENV_VAR}` substitution
- `.gitignore` excludes `settings.local.json` and `*.local.yaml`
- MCP server is localhost-only by default

---

## 9. Extending the System

### 9.1 Adding a New Agent

```python
from core.agent import BaseAgent

class MyNewAgent(BaseAgent):
    agent_name = "my_new"
    output_schema = { ... }
    input_schema = { ... }

    def system_prompt(self, input_data):
        return "You are..."

    def _register_default_tools(self):
        self.tools.register(name="my_tool", fn=my_function)
```

Then add to the pipeline:
```python
orchestrator.add_stage("my_new", MyNewAgent(observer=observer))
```

### 9.2 Adding a New Platform Publisher

```python
from tools.publishers.base import BasePublisher, PublishResult

class MyPlatformPublisher(BasePublisher):
    def __init__(self, config):
        super().__init__(config)
        self.name = "my-platform"

    def validate_config(self):
        return bool(self.config.get("api_key"))

    def publish(self, title, content, tags=None):
        # API call...
        return PublishResult(platform=self.name, success=True, url="...")
```

Then register in `config/platforms.yaml`:
```yaml
my-platform:
  enabled: true
  api_key: "${MY_PLATFORM_KEY}"
```

### 9.3 Adding a Custom Workflow

```python
from core.pipeline import PipelineOrchestrator

orchestrator = PipelineOrchestrator(observer)
orchestrator.add_stage("stage1", agent1)
orchestrator.add_stage("stage2", agent2)
result = orchestrator.run(input_data)
```

---

## Appendix: Architectural Trade-offs Summary

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Agent framework | Custom | LangChain/CrewAI | Demonstrate depth, not library skill |
| Communication | JSON Schema | Free text | Contract enforcement at low cost |
| Orchestration | Pipeline | DAG/Mesh | Correct simplicity for linear flow |
| Storage | JSON Lines | SQLite | Append-only data model |
| LLM | Claude (Sonnet) | GPT-4o | Ecosystem alignment with Claude Code |
| Protocol | MCP | Custom API | Industry standard, growing adoption |
| Retry | Agent-level | Pipeline-level | Localize error handling |
| Config | YAML | JSON/TOML | Readability for humans |
| Testing | Mock client | Integration tests | Fast iteration, no API costs |

---

> *This architecture document is a living artifact. As the system evolves, this document should be updated to reflect new decisions and trade-offs.*
