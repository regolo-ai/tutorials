#!/bin/bash
# One-click launcher for Closed-Loop Secure Coding Agent (Open SWE + Deepsec + Cognee + Regolo)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Check if .env exists, if not copy from .env.example
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Launch Python TUI
python3 main.py "$@"
