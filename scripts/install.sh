#!/bin/bash
#
# Install Agent Daily Publisher
#
# Usage:
#   ./scripts/install.sh              # install dependencies
#   ./scripts/install.sh --dev        # install with dev dependencies
#   ./scripts/install.sh --hooks      # install + configure Claude Code hooks
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "================================================"
echo "  Agent Daily Publisher — Setup"
echo "================================================"
echo ""

# Create virtualenv if not exists
if [ ! -d ".venv" ]; then
    echo "→ Creating Python virtual environment..."
    python3 -m venv .venv
    echo "  ✓ Virtual environment created"
else
    echo "- Virtual environment already exists"
fi

# Activate
source .venv/bin/activate
echo "→ Python: $(python3 --version)"

# Install dependencies
echo "→ Installing dependencies..."
pip install --quiet anthropic pyyaml requests 2>&1 | tail -1
echo "  ✓ Core dependencies installed"

if [ "${1:-}" = "--dev" ] || [ "${2:-}" = "--dev" ]; then
    pip install --quiet pytest pytest-asyncio 2>&1 | tail -1
    echo "  ✓ Dev dependencies installed"
fi

# Create data directories
mkdir -p data/sessions data/articles data/published data/traces data/logs data/memory
echo "  ✓ Data directories created"

# Create .gitkeep files
for dir in data/sessions data/articles data/published data/traces data/memory data/logs; do
    touch "$dir/.gitkeep"
done

# Setup hooks if requested
if [ "${1:-}" = "--hooks" ] || [ "${2:-}" = "--hooks" ]; then
    echo ""
    bash scripts/setup-hooks.sh
fi

echo ""
echo "================================================"
echo "  Setup complete!"
echo "================================================"
echo ""
echo "Quick start:"
echo "  source .venv/bin/activate"
echo "  python -m workflows.daily_pipeline          # dry run"
echo "  python -m workflows.daily_pipeline --publish # live"
echo ""
echo "To configure platforms, edit: config/platforms.yaml"
echo "To set up daily cron:"
echo "  crontab -e"
echo "  0 18 * * * $(pwd)/scripts/daily-run.sh --publish"
echo ""
