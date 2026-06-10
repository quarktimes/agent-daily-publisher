#!/bin/bash
#
# Setup Claude Code hooks for automatic session capture.
#
# This installs a PostMessage hook that captures each Claude Code
# interaction and appends it to the daily session log.
#
# Usage:
#   ./scripts/setup-hooks.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up Claude Code hooks for Agent Daily Publisher..."
echo ""

# Create the capture turn script
CAPTURE_SCRIPT="$PROJECT_DIR/scripts/capture-turn.py"

cat > "$CAPTURE_SCRIPT" << 'PYEOF'
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
PYEOF

chmod +x "$CAPTURE_SCRIPT"

# Create/update the Claude Code settings
SETTINGS_FILE="$PROJECT_DIR/.claude/settings.local.json"

if [ ! -f "$SETTINGS_FILE" ]; then
    mkdir -p "$(dirname "$SETTINGS_FILE")"
    echo "{}" > "$SETTINGS_FILE"
fi

# Merge hooks config into settings
python3 -c "
import json

settings_file = '$SETTINGS_FILE'
with open(settings_file, 'r') as f:
    settings = json.load(f)

hooks = settings.get('hooks', {})
post_cmd = '$CAPTURE_SCRIPT'

if 'PostMessage' not in hooks or hooks['PostMessage'].get('command') != post_cmd:
    hooks['PostMessage'] = {
        'command': f'python3 {post_cmd}'
    }
    settings['hooks'] = hooks
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    print('✓ PostMessage hook installed')
else:
    print('- PostMessage hook already configured')
"

echo ""
echo "PostMessage hook installed at: $CAPTURE_SCRIPT"
echo ""
echo "Now every Claude Code interaction will be captured for the daily summary."
echo "To verify: cat $PROJECT_DIR/data/sessions/\$(date +%Y-%m-%d).jsonl"
echo ""
echo "To set up daily cron:"
echo "  0 18 * * * $PROJECT_DIR/scripts/daily-run.sh --publish >> $PROJECT_DIR/data/logs/cron.log 2>&1"
