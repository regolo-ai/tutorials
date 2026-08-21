#!/bin/bash
# Setup script for Closed-Loop Secure Coding Agent

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo "============================================================"
echo " Setting up Closed-Loop Secure Coding Agent environment"
echo " Open SWE + Deepsec + Cognee + Brick (brick-complexity-pro)"
echo "============================================================"

# Ensure .env exists
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Install requirements
echo "Installing dependencies..."
python3 -m pip install -r requirements.txt

chmod +x run.sh setup.sh

echo "============================================================"
echo " Setup complete! Launch the TUI by running: ./run.sh"
echo "============================================================"
