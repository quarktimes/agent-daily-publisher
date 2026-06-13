"""
Pipeline State — track which stages have completed for resumable runs.

Each stage's output is cached to disk. On resume, completed stages are
skipped and cached outputs are loaded. Only failed/uncompleted stages
re-execute.

This is the key enabler for:
  - Publishing failure recovery (rerun finishes what failed)
  - Incremental development (rerun after code changes)
  - Cost savings (don't regenerate passable content)
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PipelineState:
    """Persistent state for a single pipeline run (one date)."""

    def __init__(self, date_str: str, state_dir: str | None = None):
        self.date_str = date_str
        self.state_dir = state_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "pipeline_state"
        )
        Path(self.state_dir).mkdir(parents=True, exist_ok=True)
        self._state_file = os.path.join(self.state_dir, f"{date_str}.json")
        self._state: dict = self._load()

    def _load(self) -> dict:
        """Load existing state or create empty."""
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "date": self.date_str,
            "completed_stages": [],
            "outputs": {},
            "errors": {},
            "publish_results": {},
        }

    def _save(self):
        """Persist state to disk."""
        with open(self._state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2, default=str)

    def is_completed(self, stage_name: str) -> bool:
        """Check if a stage has been completed successfully."""
        return stage_name in self._state.get("completed_stages", [])

    def get_output(self, stage_name: str) -> Any:
        """Get cached output of a completed stage."""
        return self._state.get("outputs", {}).get(stage_name)

    def complete_stage(self, stage_name: str, output: Any = None):
        """Mark a stage as completed and cache its output."""
        if stage_name not in self._state["completed_stages"]:
            self._state["completed_stages"].append(stage_name)
        if output is not None:
            self._state["outputs"][stage_name] = _serializable(output)
        if stage_name in self._state.get("errors", {}):
            del self._state["errors"][stage_name]
        self._save()

    def fail_stage(self, stage_name: str, error: str):
        """Mark a stage as failed."""
        self._state["errors"][stage_name] = error
        # Remove from completed if it was there
        if stage_name in self._state.get("completed_stages", []):
            self._state["completed_stages"].remove(stage_name)
        self._save()

    def record_publish_result(self, platform: str, success: bool, url: str = "", error: str = ""):
        """Record a single platform's publish result."""
        self._state["publish_results"][platform] = {
            "success": success,
            "url": url,
            "error": error,
        }
        self._save()

    def get_publish_results(self) -> dict:
        """Get all publish results."""
        return self._state.get("publish_results", {})

    def get_pending_publishes(self, all_platforms: list[str]) -> list[str]:
        """Get platforms that haven't been successfully published yet."""
        results = self.get_publish_results()
        pending = []
        for platform in all_platforms:
            r = results.get(platform, {})
            if not r.get("success"):
                pending.append(platform)
        return pending

    def has_any_publish_succeeded(self) -> bool:
        """Check if at least one platform published successfully."""
        return any(r.get("success") for r in self._state.get("publish_results", {}).values())

    def reset_publish_state(self):
        """Clear publish results for a retry."""
        self._state["publish_results"] = {}
        self._save()

    def summary(self) -> str:
        """Human-readable summary of current state."""
        parts = [f"Pipeline state for {self.date_str}"]
        completed = self._state.get("completed_stages", [])
        errors = self._state.get("errors", {})
        if completed:
            parts.append(f"  ✅ Completed: {', '.join(completed)}")
        if errors:
            parts.append(f"  ❌ Errors: {errors}")
        pub = self._state.get("publish_results", {})
        if pub:
            ok = [p for p, r in pub.items() if r.get("success")]
            fail = [p for p, r in pub.items() if not r.get("success")]
            if ok:
                parts.append(f"  📤 Published: {', '.join(ok)}")
            if fail:
                parts.append(f"  ❌ Failed: {', '.join(fail)}")
        return "\n".join(parts)

    def clear(self):
        """Delete state file (start fresh)."""
        if os.path.exists(self._state_file):
            os.remove(self._state_file)
        self._state = {
            "date": self.date_str,
            "completed_stages": [],
            "outputs": {},
            "errors": {},
            "publish_results": {},
        }


def _serializable(obj: Any) -> Any:
    """Convert complex objects to JSON-serializable form."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serializable(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serializable(v) for k, v in obj.items()}
    # For anything else, try string representation
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
