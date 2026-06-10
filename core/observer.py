"""
Observer — Observability protocol for agent runs.

Every agent operation is recorded: inputs, outputs, duration, errors,
tool calls, and token usage. This data is the foundation of:
  - Debugging (what did the agent think?)
  - Optimization (which agent is slow/expensive?)
  - Evaluation (is the system improving?)
  - Audit (what was published and why?)
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Observer:
    """Records agent lifecycle events for observability."""

    def __init__(self, log_dir: str | None = None):
        self.log_dir = log_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "traces"
        )
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        self._session_log: list[dict] = []

    def log(self, message: str, extra: dict | None = None):
        """Record a log message with context."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            **(extra or {}),
        }
        self._session_log.append(entry)
        logger.info(message, extra=extra)

    def record_agent_run(self, ctx: "AgentContext"):
        """Record a completed agent run."""
        ctx.duration = time.perf_counter() - ctx.start_time
        entry = {
            "type": "agent_run",
            "agent": ctx.agent_name,
            "run_id": ctx.run_id,
            "duration_seconds": round(ctx.duration, 3),
            "retry_count": ctx.retry_count,
            "token_usage": ctx.token_usage,
            "error": ctx.error,
            "timestamp": datetime.now().isoformat(),
        }
        self._session_log.append(entry)
        self._persist("agent_runs.jsonl", entry)

    def record_tool_call(self, tool_name: str, input: dict, output: Any, duration: float, error: str | None = None):
        """Record a tool invocation."""
        entry = {
            "type": "tool_call",
            "tool": tool_name,
            "input": str(input)[:500],
            "output": str(output)[:500] if output else None,
            "duration_seconds": round(duration, 3),
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        self._session_log.append(entry)
        self._persist("tool_calls.jsonl", entry)

    def record_pipeline_run(self, pipeline_name: str, stages: list[dict], duration: float, error: str | None = None):
        """Record a full pipeline execution."""
        entry = {
            "type": "pipeline_run",
            "pipeline": pipeline_name,
            "stages": stages,
            "total_duration_seconds": round(duration, 3),
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        self._session_log.append(entry)
        self._persist("pipeline_runs.jsonl", entry)

    def get_session_log(self) -> list[dict]:
        """Return all entries from the current session."""
        return self._session_log

    def _persist(self, filename: str, entry: dict):
        """Append entry to daily log file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"{date_str}_{filename}")
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning(f"Failed to persist observability data: {e}")
