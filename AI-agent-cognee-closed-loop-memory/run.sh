#!/usr/bin/env bash
# =====================================================================
# Regolo.ai + Cognee Long-Term Memory Suite Launcher
# =====================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Launch TUI
python3 main.py "$@"
