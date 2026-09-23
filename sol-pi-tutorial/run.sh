#!/usr/bin/env bash
# =====================================================================
# Regolo + SoL-Pi Benchmark Launcher
# =====================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Activate Python virtual environment if present
if [ -d ".venv" ]; then
    source ".venv/bin/activate"
fi

# Load .env if present
if [ -f ".env" ]; then
    set -a
    source ".env"
    set +a
fi

exec python3 "$DIR/sol_pi_two_arms.py" --project "$DIR" "$@"
