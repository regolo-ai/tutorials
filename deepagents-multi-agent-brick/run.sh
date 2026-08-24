#!/usr/bin/env bash
# =====================================================================
# Regolo Deep Agents: TUI Launcher Script
# =====================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Check if .venv exists and activate it
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the Green Regolo TUI
python3 main.py "$@"
