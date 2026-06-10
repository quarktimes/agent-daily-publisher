#!/bin/bash
#
# Daily Publisher Runner
# Called by cron or launchd to run the daily pipeline.
#
# Usage:
#   ./scripts/daily-run.sh              # dry run for today
#   ./scripts/daily-run.sh --publish    # live publish
#   ./scripts/daily-run.sh --date 2026-06-09 --publish
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Config
LOG_DIR="$PROJECT_DIR/data/logs"
mkdir -p "$LOG_DIR"

DATE_STR=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/daily-run-$DATE_STR.log"

# Check for virtualenv
if [ -d "$PROJECT_DIR/.venv" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily publisher..." | tee -a "$LOG_FILE"

# Run the pipeline
python -m workflows.daily_pipeline "$@" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily publisher completed successfully" | tee -a "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily publisher failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
fi

exit $EXIT_CODE
