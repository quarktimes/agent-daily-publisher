#!/usr/bin/env python3
"""
Capture Turn — PostMessage hook for Claude Code.

Called after each Claude Code response. Appends the current turn
to the daily session log for later processing by the Capture Agent.

This is a lightweight, non-blocking hook. It should never crash
or block Claude Code from responding.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Config
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sessions")
MAX_QUERY_LENGTH = 2000
MAX_RESPONSE_LENGTH = 2000


def main():
    # Read stdin for hook context
    try:
        hook_input = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except json.JSONDecodeError:
        hook_input = {}

    # Determine the current query and response
    query = hook_input.get("query", "")
    response = hook_input.get("response", "")
    project = hook_input.get("project", os.getcwd())

    # Skip empty turns
    if not query:
        return

    # Build turn record
    turn = {
        "timestamp": datetime.now().isoformat(),
        "project": project,
        "query": query[:MAX_QUERY_LENGTH],
        "response_summary": response[:MAX_RESPONSE_LENGTH],
        "query_length": len(query),
        "response_length": len(response),
    }

    # Append to daily file
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_dir = Path(DATA_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{date_str}.jsonl"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(turn, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
