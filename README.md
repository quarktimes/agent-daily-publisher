<p align="center">
  <h1 align="center">🤖 Agent Daily Publisher</h1>
  <p align="center">
    A production-grade <strong>multi-agent system</strong> that captures, analyzes, and publishes daily development logs.
    <br/>
    Built to demonstrate <strong>mastery of agent architecture</strong> — not framework wrappers.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/pattern-Multi--Agent-blueviolet"/>
  <img src="https://img.shields.io/badge/protocol-MCP-brightgreen"/>
  <img src="https://img.shields.io/badge/self--eval-Judge_loop-important"/>
</p>

---

## 🎯 Why This Exists

**Two audiences, one solution:**

1. **For me**: Automatically capture daily Claude Code sessions and publish technical blog articles to 掘金, Dev.to, Medium, etc.
2. **For interviewers**: A living portfolio piece that proves I understand **production multi-agent systems** at depth.

> "Anyone can chain LangChain calls. Few can design agent systems with evaluation loops, error recovery, and protocol-level integration."

## 🏛 Architecture at a Glance

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Capture  │→ │ Analyze  │→ │  Write   │→ ─ ─ ─ ┐
│ (Tool-   │  │ (CoT)    │  │ (Gen w/  │         │
│  Use)    │  │          │  │  Const.) │         │
└──────────┘  └──────────┘  └──────────┘         │
                                          ┌──────▼──────┐
                                          │    Judge    │
                                          │ (Self-Eval) │
                                          └──────┬──────┘
                                                 │ pass
┌──────────┐  ┌──────────┐                      │
│ Publish  │← │  Adapt   │← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘
│ (ErrRec) │  │ (Transf) │
└──────────┘  └──────────┘

       ┌─────────────────────────┐
       │  Observability (MCP)    │
       └─────────────────────────┘
```

Each stage is an **autonomous agent** with its own toolset, decision-making loop, and structured output contract.

## 🧠 Six Agents, Six Patterns

| Agent | Pattern | What It Shows |
|-------|---------|---------------|
| **Capture** | Tool-Use | Dynamic tool discovery, data aggregation |
| **Analyze** | Chain-of-Thought | Multi-step reasoning, pattern extraction |
| **Write** | Generation w/ Constraints | Controlled generation, template adherence |
| **Judge** | Self-Evaluation | Quality scoring, revision feedback loop |
| **Adapt** | Transformation | Content style transfer, multi-language |
| **Publish** | Error Recovery | Retry strategies, partial failure handling |

## ✨ What Makes This Different

**Not another LangChain wrapper.** This is a **from-first-principles agent framework**:

- 🔄 **ReAct Loop** — agents think-act-observe, not call-return
- 📋 **JSON Schema Contracts** — every agent<->agent handshake is validated
- ⚖️ **Self-Evaluation Loop** — Judge Agent rejects, Write Agent revises, loop until quality
- 🔧 **Dynamic Tool Registry** — agents discover available tools at runtime
- 🔭 **Full Observability** — every decision, every tool call, every token is traceable
- 📡 **MCP Protocol** — external systems can query pipeline state
- 🛡 **Graceful Degradation** — one platform failure doesn't crash the pipeline

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/yourname/agent-daily-publisher
cd agent-daily-publisher
bash scripts/install.sh

# Dry run (no publishing)
python -m workflows.daily_pipeline

# Live publish
python -m workflows.daily_pipeline --publish

# Configure platforms
# Edit config/platforms.yaml (set enabled: true + API keys)
```

### Prerequisites

- Python 3.12+
- `ANTHROPIC_API_KEY` environment variable
- Platform API keys (for publishing)

## 📦 Project Structure

```
agent-daily-publisher/
├── core/           # Agent framework (from scratch)
│   ├── agent.py           # BaseAgent — ReAct loop
│   ├── pipeline.py        # PipelineOrchestrator + JudgeLoop
│   ├── tool_registry.py   # Dynamic tool discovery
│   ├── structured_output.py # JSON Schema enforcement
│   ├── memory.py          # Hierarchical memory management
│   └── observer.py        # Observability protocol
├── agents/         # 6 specialized agents
├── tools/          # Tools + platform connectors
├── mcp/            # MCP protocol server
├── workflows/      # Pipeline orchestration
├── templates/      # Platform-specific templates
├── config/         # YAML configuration
└── scripts/        # Install, hooks, cron
```

## 📊 Production Features

| Feature | Implementation |
|---------|---------------|
| **Error Recovery** | Exponential backoff, 3 retries, graceful degradation |
| **Observability** | JSONL traces per agent call, tool call, pipeline run |
| **Configuration** | YAML-based, no code changes for platform config |
| **Testing** | Mock Claude client for dry runs |
| **Scheduling** | cron/launchd integration via daily-run.sh |
| **Extensibility** | Add new agents via BaseAgent subclass, new platforms via BasePublisher |

## 🛠 Platform Support

| Platform | Status | Required |
|----------|--------|----------|
| Dev.to | ✅ Ready | `DEVTO_API_KEY` |
| 掘金 (Juejin) | ✅ Ready | `JUEGIN_TOKEN` |
| Medium | 🚧 Planned | `MEDIUM_TOKEN` |
| CSDN | 🚧 Planned | `CSDN_TOKEN` |
| 知乎 (Zhihu) | 🔮 Future | Cookie/API |
| 微信公众号 | 🔮 Future | WeChat MP AppID |

## 🔗 MCP Integration

Start the MCP server to query pipeline state from any MCP client:

```bash
python -m mcp.server
```

Then in Claude Code: "What articles were published today?"

## 🗺 Roadmap

- **Phase 1** ✅ Core pipeline (Capture → Analyze → Write → Judge)
- **Phase 2** ✅ Adapt + Publish agents, platform connectors
- **Phase 3** 🚧 MCP Server, full test coverage, CI/CD
- **Phase 4** 🔮 Human-in-the-loop review, A/B testing, analytics dashboard

---

<p align="center">
  <i>Built to prove I know agents — not as a framework user, but as an architect.</i>
</p>
