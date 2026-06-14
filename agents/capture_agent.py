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
        return f"""你是 Capture Agent，负责将 Claude Code 的会话数据转化为结构化 JSON。

日期：{date}

输入数据来自 Claude Code 的 history 日志和 git 提交记录。请分析并生成结构化摘要，包含：
  - 今天有哪些会话（项目、提问、标签）
  - 有哪些 git 变更
  - 当天工作的简要概述

要求：
  - 简洁但完整。根据提问内容推断 session 标签
  - 如果某个 session 没有 git 数据，省略 git_commits 字段
  - 输出中的 date 必须是 {date}
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        sessions = output.get("sessions", [])
        output["total_prompts"] = sum(len(s.get("prompts", [])) for s in sessions)
        output["projects"] = list(set(s.get("project", "") for s in sessions if s.get("project")))
        if not output.get("summary") and sessions:
            project_names = ", ".join(output["projects"][:3])
            output["summary"] = f"Captured {output['total_prompts']} interactions across {len(sessions)} sessions ({project_names})"
        return output
