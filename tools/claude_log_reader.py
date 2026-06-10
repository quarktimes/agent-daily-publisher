"""
Claude Code Log Reader — Extract session data from Claude Code logs.

Claude Code 2.1.143+ stores sessions differently:
  - OLD: ~/.claude/history.jsonl (flat, one entry per prompt)
  - NEW: ~/.claude/projects/<hash>/<session-id>.jsonl (one file per session)
    Each line has {type, message, timestamp, sessionId, cwd, ...}
    types: user (prompts), assistant (responses), tool_use, etc.

This reader tries both sources and merges results.
"""

import glob
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLAUDE_HISTORY_PATH = os.path.expanduser("~/.claude/history.jsonl")
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")


# ====================================================================
# NEW FORMAT READER — per-session JSONL files
# ====================================================================

def load_sessions_for_date(date_str: str | None = None) -> list[dict]:
    """
    Load ALL sessions for a given date from per-session JSONL files.

    Scans ~/.claude/projects/*/*.jsonl, parses user messages,
    groups by session, and returns structured session data.

    Args:
        date_str: YYYY-MM-DD format, defaults to today

    Returns:
        List of session dicts with prompts, project paths, etc.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    sessions_map: dict[str, dict] = {}

    # Scan all project session files
    session_files = glob.glob(os.path.join(CLAUDE_PROJECTS_DIR, "*", "*.jsonl"))

    for filepath in session_files:
        session_id = Path(filepath).stem
        prompts = []
        cwd = ""
        version = ""
        timestamp_first = None

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                ts = entry.get("timestamp", "")

                # Check date
                if not ts or not ts.startswith(date_str):
                    continue

                # Record session metadata
                if entry_type == "user":
                    message = entry.get("message", {})
                    content = message.get("content", "") if isinstance(message, dict) else ""
                    cwd = entry.get("cwd", cwd) or entry.get("cwd", "")
                    version = entry.get("version", version) or entry.get("version", "")
                    if not timestamp_first:
                        timestamp_first = ts

                    prompts.append({
                        "query": content[:500] if isinstance(content, str) else str(content)[:500],
                        "timestamp": ts,
                        "session_id": session_id,
                    })

        if prompts:
            # Infer project name from cwd or directory name
            project_name = os.path.basename(cwd) if cwd else Path(filepath).parent.name

            if session_id not in sessions_map:
                sessions_map[session_id] = {
                    "session_id": session_id,
                    "project": cwd or project_name,
                    "project_name": project_name,
                    "start_time": timestamp_first or "",
                    "version": version,
                    "prompts": [],
                    "git_commits": [],
                    "tags": [],
                }

            sessions_map[session_id]["prompts"].extend(prompts)
            sessions_map[session_id]["start_time"] = sessions_map[session_id]["start_time"] or timestamp_first or ""

    # Convert map to list, sort by start time
    sessions = list(sessions_map.values())
    sessions.sort(key=lambda s: s.get("start_time", ""))

    # Compute tags per session from prompts
    for session in sessions:
        all_text = " ".join(p.get("query", "") for p in session.get("prompts", []))
        session["tags"] = _infer_tags(all_text)

    return sessions


# ====================================================================
# OLD FORMAT READER — flat history.jsonl (fallback)
# ====================================================================

def load_history_for_date(date_str: str | None = None, history_path: str = CLAUDE_HISTORY_PATH) -> list[dict]:
    """
    Load from the old flat history.jsonl format.
    Only returns non-empty result if the new format finds nothing.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # First try the new format
    sessions = load_sessions_for_date(date_str)
    if sessions:
        return sessions

    # Fallback to old format
    if not os.path.exists(history_path):
        return []

    entries = []
    seen_queries = set()
    min_interval_ms = 60_000

    with open(history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = entry.get("timestamp", 0)
            entry_date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if entry_date != date_str:
                continue

            display_text = entry.get("display", "")
            if display_text in seen_queries:
                continue

            project = entry.get("project", "")
            full_text = display_text
            pasted = entry.get("pastedContents", {})
            for pid, pc in pasted.items():
                if isinstance(pc, dict) and pc.get("content"):
                    full_text += f"\n{pc['content']}"

            entries.append({
                "timestamp": ts,
                "datetime": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
                "display": display_text,
                "full_text": full_text,
                "project": project,
                "tags": _infer_tags(display_text),
            })
            seen_queries.add(display_text)

    entries.sort(key=lambda e: e["timestamp"])

    if entries:
        # Wrap in session format for compatibility
        return [{
            "session_id": "history_legacy",
            "project": entries[0].get("project", ""),
            "project_name": Path(entries[0].get("project", "")).name if entries[0].get("project") else "",
            "start_time": entries[0].get("datetime", ""),
            "prompts": [{"query": e.get("display", "")} for e in entries],
            "tags": list(set(t for e in entries for t in e.get("tags", []))),
        }]

    return []


# ====================================================================
# SHARED UTILITIES
# ====================================================================

def _infer_tags(text: str) -> list[str]:
    """Infer tags from text."""
    tags = []
    text_lower = text.lower()

    if any(w in text_lower for w in ["bug", "fix", "error", "issue", "修复", "问题"]):
        tags.append("bug-fix")
    if any(w in text_lower for w in ["feature", "add", "new", "实现", "添加", "功能"]):
        tags.append("feature")
    if any(w in text_lower for w in ["refactor", "重构", "优化", "clean"]):
        tags.append("refactor")
    if any(w in text_lower for w in ["test", "测试"]):
        tags.append("test")
    if any(w in text_lower for w in ["doc", "文档", "readme"]):
        tags.append("documentation")
    if any(w in text_lower for w in ["deploy", "ci", "cd", "发布", "部署"]):
        tags.append("devops")
    if any(w in text_lower for w in ["review"]):
        tags.append("review")
    if any(w in text_lower for w in ["config", "配置", "setup"]):
        tags.append("configuration")
    if any(w in text_lower for w in ["agent", "ai", "llm", "claude"]):
        tags.append("ai")
    if any(w in text_lower for w in ["python", "django", "flask"]):
        tags.append("python")

    return tags


def group_by_project(entries: list[dict]) -> dict[str, list[dict]]:
    """Group session entries by project path."""
    groups = {}
    for entry in entries:
        project = entry.get("project", "unknown")
        if project not in groups:
            groups[project] = []
        groups[project].append(entry)
    return groups


def load_project_log_for_date(project_dir: str, date_str: str | None = None) -> list[dict]:
    """Load per-project session files matching a project path."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Find the project hash directory
    project_hash = _hash_project_path(project_dir)
    log_dir = os.path.join(CLAUDE_PROJECTS_DIR, project_hash)

    if not os.path.exists(log_dir):
        return []

    entries = []
    for fname in os.listdir(log_dir):
        if fname.endswith(".jsonl"):
            fpath = os.path.join(log_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            ts = entry.get("timestamp", "")
                            if ts.startswith(date_str):
                                entries.append(entry)
                        except json.JSONDecodeError:
                            continue
            except (OSError, UnicodeDecodeError):
                continue

    return entries


def _hash_project_path(path: str) -> str:
    """Convert project path to Claude Code's project directory hash format."""
    cleaned = path.rstrip("/").lstrip("/")
    parts = cleaned.split("/")
    return "-" + "-".join(parts)
