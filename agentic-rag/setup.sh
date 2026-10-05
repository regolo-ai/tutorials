#!/usr/bin/env bash
set -e

green_color="\033[1;32m"
reset_color="\033[0m"

echo -e "${green_color}"
cat << "EOF"
██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗ 
██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗
██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║
██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║
██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝
╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ 
EOF
echo -e "${reset_color}"

echo "regolo agentic rag environment configuration script."
echo "default orchestration model: brick-complexity-pro."

# check if python3 exists on the host system
if ! command -v python3 &> /dev/null; then
    echo "error: python3 is not installed on this system."
    exit 1
fi

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$script_dir"

# locate existing local virtual environment or set default path
detected_venv=""
if [ -n "$VIRTUAL_ENV" ] && [ -d "$VIRTUAL_ENV" ]; then
    detected_venv="$VIRTUAL_ENV"
elif [ -d ".venv" ]; then
    detected_venv=".venv"
elif [ -d "venv" ]; then
    detected_venv="venv"
elif [ -d "env" ]; then
    detected_venv="env"
fi

if [ -n "$detected_venv" ]; then
    echo "existing local virtual environment detected: $detected_venv"
    echo "activating detected local environment and installing required modules:"
    if [ "$VIRTUAL_ENV" != "$detected_venv" ]; then
        if [ -f "$detected_venv/bin/activate" ]; then
            source "$detected_venv/bin/activate"
        fi
    fi
    pip install -r requirements.txt -q
    echo "python dependencies successfully verified in: $detected_venv"
    active_env="$detected_venv"
else
    active_env=".venv"
    echo "no existing local environment found: creating new virtual environment in $active_env"
    python3 -m venv "$active_env"
    source "$active_env/bin/activate"
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    echo "created and installed python modules into new environment: $active_env"
fi

# create local environment file from example if missing
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "created local configuration file: .env (copied from .env.example)"
    else
        echo "regolo_api_key=" > .env
        echo "regolo_model=brick-complexity-pro" >> .env
        echo "regolo_base_url=https://api.regolo.ai/v1" >> .env
        echo "created local configuration file: .env"
    fi
fi

echo ""
echo "setup completed successfully: launching interactive menu options now."
echo ""

# launch interactive menu directly so developer gets options immediately
exec python3 main.py "$@"
