#!/usr/bin/env bash
# ==============================================================================
# REGOLO CodeOps ZDR — OpenHarness
# Harness Engineering · Open Models · EU Zero Data Retention
# https://github.com/regolo-ai/tutorials/harness-agent-zero-data-retention
# ==============================================================================
set -e

# Resolve repository root directory
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ [ERROR] python3 is required but not installed." >&2
    exit 1
fi

VENV_DIR="$REPO_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# Bootstrap virtual environment if missing
if [ ! -f "$VENV_PY" ]; then
    echo "⚡ [REGOLO] Setting up local Python environment (.venv)..."
    python3 -m venv "$VENV_DIR"
    "$VENV_PIP" install --upgrade pip -q
    if [ -f "$REPO_DIR/requirements.txt" ]; then
        echo "⚡ [REGOLO] Installing dependencies from requirements.txt..."
        "$VENV_PIP" install -r "$REPO_DIR/requirements.txt" -q
    fi
fi

# Bootstrap .env if missing
if [ ! -f "$REPO_DIR/.env" ] && [ -f "$REPO_DIR/.env.example" ]; then
    echo "⚡ [REGOLO] Bootstrapping .env configuration from .env.example..."
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
fi

# Export PYTHONPATH so regolo_agent_stack is directly importable without package installation
export PYTHONPATH="$REPO_DIR:$PYTHONPATH"

# Command dispatching
if [ $# -gt 0 ]; then
    if [ "$1" = "tui" ]; then
        exec "$VENV_PY" -m regolo_agent_stack.tui
    else
        exec "$VENV_PY" -m regolo_agent_stack.cli "$@"
    fi
else
    # Default behavior without arguments: launch interactive TUI
    exec "$VENV_PY" -m regolo_agent_stack.tui
fi
