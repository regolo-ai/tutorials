#!/usr/bin/env bash
# =====================================================================
# Regolo Deep Agents: Environment Setup Script
# =====================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "============================================================"
echo "⚡ REGOLO DEEP AGENTS • ENVIRONMENT SETUP ⚡"
echo "============================================================"

# 1. Check Python version
python3 -c "import sys; assert sys.version_info >= (3, 9), 'Python 3.9+ required'"
echo "✔ Python $(python3 --version | cut -d' ' -f2) verified."

# 2. Setup Virtualenv if not present
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
fi

# 3. Activate Virtualenv
source .venv/bin/activate

# 4. Install Dependencies
echo "Installing dependencies from requirements.txt..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

# 5. Setup .env file
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

echo ""
echo "============================================================"
echo "✔ Setup Completed Successfully!"
echo "To start the Regolo Green TUI, run:"
echo "  ./run.sh"
echo "============================================================"
