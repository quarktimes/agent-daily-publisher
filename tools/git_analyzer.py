"""
Git Analyzer — Extract code change context from git repositories.

For each project that Claude Code worked on today, this tool:
  1. Finds the git repo
  2. Gets today's commit log
  3. Gets file diffs for changed files
  4. Summarizes what changed and why

This is what gives the published articles actual code-level depth,
not just "I worked on X" but "I changed Y because Z."
"""

import os
import subprocess
from datetime import datetime
from typing import Any


def get_today_git_log(repo_path: str, date_str: str | None = None) -> list[dict]:
    """Get git commits for a repo for a given date."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(os.path.join(repo_path, ".git")):
        return []

    try:
        result = subprocess.run(
            [
                "git", "log",
                f"--since={date_str}T00:00:00",
                f"--until={date_str}T23:59:59",
                "--format=%H|%an|%s|%ai",
                "--shortstat",
            ],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    return _parse_git_log(result.stdout)


def _parse_git_log(raw: str) -> list[dict]:
    """Parse git log --shortstat output into structured entries."""
    commits = []
    lines = raw.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            commit = {
                "hash": parts[0][:12],
                "author": parts[1],
                "message": parts[2],
                "date": parts[3],
                "files_changed": 0,
                "insertions": 0,
                "deletions": 0,
            }
            # Next line is shortstat
            i += 1
            if i < len(lines):
                stat = lines[i].strip()
                commit["files_changed"] = _extract_number(stat, "file") or 0
                commit["insertions"] = _extract_number(stat, "insertion") or 0
                commit["deletions"] = _extract_number(stat, "deletion") or 0
                i += 1
            commits.append(commit)
        else:
            i += 1
    return commits


def get_commit_diff(repo_path: str, commit_hash: str) -> str | None:
    """Get the full diff for a specific commit."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{commit_hash}^..{commit_hash}", "--stat"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout[:3000]  # truncate for token budget
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def get_today_changed_files(repo_path: str, date_str: str | None = None) -> list[str]:
    """Get list of files changed today."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        result = subprocess.run(
            [
                "git", "diff",
                f"$(git rev-list --max-parents=0 HEAD)",  # from root
                "--name-only",
                f"--since={date_str}T00:00:00",
            ],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=15,
            shell=True,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def _extract_number(text: str, word: str) -> int:
    """Extract number before a keyword, e.g., '3 files changed' -> 3."""
    import re
    pattern = rf"(\d+)\s+{word}"
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0
