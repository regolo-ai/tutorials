#!/usr/bin/env bash
# ==============================================================================
# Baco Scanner TUI Launcher (Regolo.ai Edition)
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

# Launch standalone Python TUI
exec python3 "$DIR/baco_tui.py" "$@"
