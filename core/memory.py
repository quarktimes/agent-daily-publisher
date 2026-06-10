"""Agent Memory — hierarchical memory management for agents.

Three-tier memory system:
  1. Session memory — current run only (short-term, ephemeral)
  2. Day memory — all runs today (medium-term, file-backed)
  3. Project memory — cross-day patterns (long-term, persistent)

This design prevents context-window overflow while preserving
important context across agent runs.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class AgentMemory:
    """Hierarchical memory for agents."""

    def __init__(self, memory_dir: str | None = None):
        self.memory_dir = memory_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "memory"
        )
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)
        self._session: list[dict] = []

    # --- Session memory (ephemeral) ---

    def remember(self, key: str, value: Any):
        """Store a value in session memory."""
        self._session.append({"key": key, "value": value, "timestamp": datetime.now().isoformat()})

    def recall(self, key: str) -> list[Any]:
        """Retrieve all values for a key in session memory."""
        return [entry["value"] for entry in self._session if entry["key"] == key]

    # --- Day memory (file-backed) ---

    def save_day(self, key: str, data: Any):
        """Save data to today's memory file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(self.memory_dir, f"day_{date_str}.jsonl")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "data": data, "timestamp": datetime.now().isoformat()}, ensure_ascii=False) + "\n")

    def load_day(self, key: str | None = None) -> list[dict]:
        """Load today's memory entries, optionally filtered by key."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(self.memory_dir, f"day_{date_str}.jsonl")
        if not os.path.exists(filepath):
            return []
        results = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if key is None or entry["key"] == key:
                    results.append(entry)
        return results

    # --- Project memory (cross-day) ---

    def save_project(self, key: str, data: Any):
        """Save data to long-term project memory."""
        filepath = os.path.join(self.memory_dir, "project_memory.jsonl")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "data": data, "timestamp": datetime.now().isoformat()}, ensure_ascii=False) + "\n")

    def load_project(self, key: str) -> list[dict]:
        """Load project memory entries by key."""
        filepath = os.path.join(self.memory_dir, "project_memory.jsonl")
        if not os.path.exists(filepath):
            return []
        results = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry["key"] == key:
                        results.append(entry)
                except json.JSONDecodeError:
                    continue
        return results
