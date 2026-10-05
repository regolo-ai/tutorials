#!/usr/bin/env bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$script_dir"

# verify or initialize local python environment
if [ ! -d ".venv" ]; then
    echo "running initial setup script to create local environment:"
    ./setup.sh
fi

source .venv/bin/activate

# execute baseline e2e verification test
echo "executing base verification test:"
python3 main.py --sample-test
echo "initialization completed successfully."
