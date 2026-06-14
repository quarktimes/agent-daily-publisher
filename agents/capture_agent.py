"""
Capture Agent — Tool-Use Pattern

This agent demonstrates the Tool-Use pattern:
  1. Agent discovers available tools via ToolRegistry
  2. Tools are called to gather raw data
  3. LLM structures the raw data into the output schema

The agent autonomously decides how to find and aggregate session data,
rather than following hard-coded steps.

IMPLEMENTATION NOTE:
  Data gathering uses registered tools (procedurally collected for reliability).
  The LLM is then used to structure/narrate the findings.
  In a full implementation, the tool loop would be fully autonomous.
"""

import os
from datetime import datetime
from typing import Any

from core.agent import BaseAgent, AgentContext
from core.structured_output import SchemaValidator
from core.tool_registry import ToolRegistry
from tools.claude_log_reader import load_history_for_date, group_by_project
from tools.git_analyzer import get_today_git_log


# Schema for individual session output
SESSION_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "project": {"type": "string"},
        "start_time": {"type": "string"},
        "duration_minutes": {"type": "number"},
        "prompts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "summary": {"type": "string"},
                    "files_changed": {"type": "array", "items": {"type": "string"}},
                    "key_decisions": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "git_commits": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["session_id", "project"],
}

# Schema for the full capture output
CAPTURE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "sessions": {
            "type": "array",
            "items": SESSION_SCHEMA,
        },
        "total_prompts": {"type": "integer"},
        "projects": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["date", "sessions"],
}

CAPTURE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
    },
    "required": ["date"],
}


class CaptureAgent(BaseAgent):
    """
    Captures raw session data from Claude Code logs and git history.

    Agent Pattern: Tool-Use
      - Registers tools for data gathering (log reader, git analyzer)
      - Uses LLM to structure raw data into the output schema
      - Handles missing/partial data gracefully
    """

    agent_name = "capture"
    output_schema = CAPTURE_OUTPUT_SCHEMA
    input_schema = CAPTURE_INPUT_SCHEMA

    # Note: data is gathered procedurally in run(), not via tool loop.
    # The tools (load_history, get_git_log) are imported and called directly
    # to avoid multi-round tool-loop reliability issues with some API providers.

    def run(self, input_data: Any) -> dict[str, Any]:
        """
        Execute capture: gather data via tools, then structure with LLM.

        Phase 1: Procedural data collection (tool execution)
        Phase 2: LLM structuring into output schema
        """
        ctx = AgentContext(self.agent_name, input_data)
        date = input_data.get("date", datetime.now().strftime("%Y-%m-%d"))

        try:
            # ---- Phase 1: Data Collection (procedural tool use) ----
            self.observer.log(f"[capture] Gathering data for {date}", extra={"run_id": ctx.run_id})

            # Tool 1: Load history
            history_entries = load_history_for_date(date)
            self.observer.log(f"[capture] Found {len(history_entries)} history entries")

            # Tool 2: Group by project
            grouped = group_by_project(history_entries)

            # Tool 3: Get git logs for each project
            git_data = {}
            for project in grouped:
                if project and os.path.exists(os.path.join(project, ".git")):
                    commits = get_today_git_log(project, date)
                    if commits:
                        git_data[project] = commits

            # ---- Phase 2: LLM Structuring (skip if no data) ----
            if not history_entries:
                self.observer.log(f"[capture] No history entries found for {date} — returning empty result")
                output = {
                    "date": date,
                    "sessions": [],
                    "total_prompts": 0,
                    "projects": [],
                    "summary": f"No Claude Code sessions recorded on {date}",
                }
                ctx.output = output
                self.observer.record_agent_run(ctx)
                return output

            prompt = self.system_prompt(input_data)

            tool_context = {
                "date": date,
                "history_entries": history_entries[:50],
                "projects_found": list(grouped.keys()),
                "git_commits": git_data,
                "total_entries": len(history_entries),
            }

            self.observer.log(f"[capture] Running LLM analysis...")
            ctx.input = tool_context  # Feed collected data as LLM context
            output = self._call_llm(prompt, ctx)

            # Validate output schema
            if self.output_schema:
                validator = SchemaValidator(self.output_schema)
                try:
                    output = validator.validate(output)
                except Exception:
                    # LLM produced partial output — fill in defaults
                    output.setdefault("sessions", [])
                    output.setdefault("total_prompts", len(history_entries))
                    output.setdefault("projects", list(set(e.get("project", "") for e in history_entries)))
                    output["date"] = date
                    if not output.get("summary"):
                        output["summary"] = f"Captured {len(history_entries)} interactions"

            output = self.process_result(output, ctx)
            ctx.output = output
            self.observer.record_agent_run(ctx)
            return output

        except Exception as e:
            ctx.error = str(e)
            self.observer.record_agent_run(ctx)
            raise

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        return f"""你是 Capture Agent，将 Claude Code 的原始会话及 git 数据转化为结构化 JSON。

日期：{date}

## 输入数据类型
你会收到两类数据：
1. **history_entries** — Claude Code 会话列表（含 display、full_text、project、timestamp）
2. **git_commits** — 每个项目的 git 提交记录（含 hash、message、files_changed）

## 输出要求 — 必须严格按以下 JSON 结构

```json
{{
  "date": "{date}",
  "sessions": [
    {{
      "session_id": "项目路径的哈希或 UUID",
      "project": "/Users/xxx/项目名",
      "project_name": "项目名",
      "start_time": "2026-06-14T09:00:00",
      "duration_minutes": 估算的持续时间,
      "prompts": [
        {{
          "query": "用户的提问内容（截断到200字）",
          "summary": "这轮对话做了什么，一句话总结",
          "timestamp": "具体时间",
          "tags": ["分类标签"]
        }}
      ],
      "git_commits": [
        {{
          "hash": "abc123",
          "message": "commit 信息",
          "files_changed": 3,
          "insertions": 15,
          "deletions": 5
        }}
      ]
    }}
  ]
}}
```

## 标签推断规则 — 严格按此分类

根据 query 内容判断，一个 session 可以有多个标签：

| 关键词匹配 | 标签 |
|-----------|------|
| bug/fix/error/issue/修复/问题/报错 | bug-fix |
| feature/add/new/实现/添加/新增/功能 | feature |
| refactor/重构/优化/clean/整理 | refactor |
| test/测试/单测/集成测试 | test |
| doc/文档/readme/注释 | documentation |
| deploy/ci/cd/发布/部署/上线 | devops |
| review/review/审核 | review |
| config/配置/setup/环境 | configuration |
| agent/ai/llm/gpt/claude/rag/embedding | ai |
| 数据库/sql/redis/mongo/mysql/sql | database |
| 前端/vue/react/css/html/ui | frontend |
| 后端/api/spring/django/fastapi | backend |

## 质量自检 — 输出前逐项确认

- [ ] 所有有内容的 session 都已纳入 sessions 数组
- [ ] 每个 session 的 prompts 非空
- [ ] 标签至少有 1 个
- [ ] 没有 git 数据的 session，git_commits 字段为空数组 [] 而非省略
- [ ] date 字段 = {date}
- [ ] 同一个 session 内重复的 query 已去重（timestamp 间隔 <60s 的相同内容视为重复）
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        sessions = output.get("sessions", [])
        output["total_prompts"] = sum(len(s.get("prompts", [])) for s in sessions)
        output["projects"] = list(set(s.get("project", "") for s in sessions if s.get("project")))
        if not output.get("summary") and sessions:
            project_names = ", ".join(output["projects"][:3])
            output["summary"] = f"Captured {output['total_prompts']} interactions across {len(sessions)} sessions ({project_names})"
        return output
