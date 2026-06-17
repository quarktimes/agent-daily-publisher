# Agent Daily Publisher — CLAUDE.md

## Project Overview
A multi-agent system that captures daily Claude Code sessions, processes them into technical blog articles, and publishes to social media platforms. Built as a demonstration of production-grade agent architecture for senior agent developer roles.

## Architecture
- **6 specialized agents** in a pipeline: Capture → Analyze → Write → [Judge ↻] → Adapt → Publish
- **Self-built agent framework** in `core/` (no LangChain/CrewAI)
- **MCP Server** for observability and external querying
- **Claude Code hooks** for automatic session capture

## Key Files
- `core/agent.py` — BaseAgent with ReAct loop
- `core/pipeline.py` — PipelineOrchestrator + JudgeLoopPipeline
- `agents/` — 6 agent implementations
- `workflows/daily_pipeline.py` — Main entry point
- `mcp/server.py` — MCP protocol server

## Commands
- `python -m workflows.daily_pipeline` — Dry run for today
- `python -m workflows.daily_pipeline --publish` — Live publish
- `python -m workflows.daily_pipeline --date YYYY-MM-DD` — Specific date
- `python -m workflows.daily_pipeline --no-judge` — Skip quality check
- `python -m mcp.server` — Start MCP server
- `bash scripts/install.sh` — Install dependencies
- `bash scripts/setup-hooks.sh` — Configure Claude Code hooks
- `bash scripts/daily-run.sh` — Cron entry point

## Dependencies
- Python 3.12+
- `anthropic` — Claude API client
- `pyyaml` — Config parsing
- `requests` — HTTP for publishers
- `mcp` — MCP protocol (optional, for server mode)

## Modification Protocol

1. **先分析** — 遇到问题先排查根因，输出方案（至少 2 个选项），不允许直接改
2. **等我确认** — 我选择方案后，你再执行修改
3. **改后验证** — 改完跑一遍 pipeline 确认效果，不允许合入未验证的代码
4. **一次改一个** — 一个 PR 只解决一个问题，不堆叠修改

## Pipeline Flow
```
Capture Agent (Tool-Use) → Analyze Agent (CoT) → Write Agent (Generation)
  → [Judge Agent (Self-Eval) ↻] → Adapt Agent (Transformation) → Publish Agent (Error Recovery)
```

## Configuration
- `config/settings.yaml` — Pipeline and API configuration
- `config/platforms.yaml` — Platform enable/disable and credentials

## Data Directory
- `data/sessions/` — Raw captured sessions
- `data/articles/` — Generated article drafts
- `data/published/` — Publication records
- `data/traces/` — Observability traces
