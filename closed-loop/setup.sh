#!/usr/bin/env bash

# ==============================================================================
#  Regolo.ai - Project Setup & Management CLI
# ==============================================================================
#  A branded, automated CLI tool to set up the environment, configure API keys,
#  manage Docker services (Qdrant), and launch the Closed-Loop Code Reviewer.
# ==============================================================================

# Exit on absolute failures or unset variables if strictly needed
set -uo pipefail

# Text formatting helper constants
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0;37m' # No Color

# Base directory setup
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"
VENV_DIR="${ROOT_DIR}/.venv"
REQUIREMENTS_FILE="${ROOT_DIR}/requirements.txt"
MAIN_PY="${ROOT_DIR}/main.py"

# Branded Banner
print_banner() {
    clear
    echo -e "${GREEN}"
    echo "  ██████╗ ███████╗ ██████╗  ██████╗ ██╗       ██████╗        █████╗ ██╗"
    echo "  ██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║      ██╔═══██╗      ██╔══██╗██║"
    echo "  ██████╔╝█████╗  ██║  ███╗██║   ██║██║      ██║   ██║█████╗███████║██║"
    echo "  ██╔══██╗██╔══╝  ██║   ██║██║   ██║██║      ██║   ██║╚════╝██╔══██║██║"
    echo "  ██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝      ██║  ██║██║"
    echo "  ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝       ╚═╝  ╚═╝╚═╝"
    echo -e "${NC}"
    echo -e " ${BOLD}⚡ REGOLO.AI - CLOSED-LOOP ENVIRONMENT MANAGER ⚡${NC}"
    echo -e " =============================================================================="
}

# Print section headers nicely
print_header() {
    echo -e "\n${BOLD}${CYAN}▶ $1${NC}"
    echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
}

# Setup Python environment
setup_python() {
    print_header "Python Environment Setup"

    # Check for python3
    if ! command -v python3 &>/dev/null; then
        echo -e "${RED}❌ Error: Python 3 is not installed on this system.${NC}"
        echo -e "   Please install Python 3.10+ and try again."
        exit 1
    fi

    # Verify python version
    PY_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    echo -e "Found Python version: ${BOLD}${GREEN}${PY_VERSION}${NC}"

    # Setup virtual environment
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "Creating virtual environment in ${BOLD}${VENV_DIR}${NC}..."
        python3 -m venv "$VENV_DIR"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Virtual environment created successfully.${NC}"
        else
            echo -e "${RED}❌ Failed to create virtual environment.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ Virtual environment already exists.${NC}"
    fi

    # Install/upgrade dependencies
    echo -e "Installing dependencies from ${BOLD}requirements.txt${NC}..."
    "$VENV_DIR/bin/pip" install --upgrade pip &>/dev/null
    "$VENV_DIR/bin/pip" install -r "$REQUIREMENTS_FILE"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Dependencies installed successfully.${NC}"
    else
        echo -e "${RED}❌ Failed to install dependencies.${NC}"
        exit 1
    fi
}

# Setup Configuration Environment File
setup_env_file() {
    print_header "Environment Settings (.env)"

    # Create .env from .env.example if not exists
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "Creating .env file from template..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo -e "${GREEN}✓ Created .env file.${NC}"
    else
        echo -e "${GREEN}✓ Existing .env file found.${NC}"
    fi

    # Check for REGOLO_API_KEY
    CURRENT_KEY=""
    if [ -f "$ENV_FILE" ]; then
        CURRENT_KEY=$(grep "REGOLO_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    fi

    if [ -z "$CURRENT_KEY" ] || [ "$CURRENT_KEY" = "your_api_key_here" ]; then
        echo -e "${YELLOW}⚠️  REGOLO_API_KEY is not set or is still the default placeholder.${NC}"
        echo -ne "${BOLD}Enter your Regolo.ai API Key:${NC} "
        read -r USER_KEY
        
        if [ -n "$USER_KEY" ]; then
            # Replace placeholder or insert
            # Avoid sed platform inconsistency by using Python helper to rewrite .env cleanly
            python3 -c "
import os
path = '$ENV_FILE'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
new_lines = []
for line in lines:
    if line.startswith('REGOLO_API_KEY='):
        new_lines.append(f'REGOLO_API_KEY={os.environ.get(\"USER_KEY_ENV\", \"\")}\n')
    else:
        new_lines.append(line)
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
" 2>/dev/null || sed -i.bak "s|REGOLO_API_KEY=.*|REGOLO_API_KEY=${USER_KEY}|g" "$ENV_FILE" 2>/dev/null
            
            # Export USER_KEY_ENV for python script
            export USER_KEY_ENV="$USER_KEY"
            python3 -c "
import os
path = '$ENV_FILE'
content = open(path).read()
if 'REGOLO_API_KEY' in content:
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('REGOLO_API_KEY='):
            lines[i] = 'REGOLO_API_KEY=' + os.environ['USER_KEY_ENV']
    open(path, 'w').write('\n'.join(lines) + '\n')
"
            echo -e "${GREEN}✓ REGOLO_API_KEY updated in .env.${NC}"
        else
            echo -e "${YELLOW}Skipped key configuration. Remember to set it manually in .env before running.${NC}"
        fi
    else
        echo -e "${GREEN}✓ REGOLO_API_KEY is configured in .env.${NC}"
    fi

    # Always prompt for Qdrant API Key and Access Configurations
    CURRENT_QDRANT_URL=$(grep "QDRANT_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    CURRENT_QDRANT_KEY=$(grep "QDRANT_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")

    if [ -z "$CURRENT_QDRANT_URL" ]; then
        CURRENT_QDRANT_URL="http://localhost:6333"
    fi

    echo -e "\n${BOLD}${CYAN}Qdrant Configuration & Access Setup:${NC}"
    echo -ne "Enter Qdrant Instance URL [${CURRENT_QDRANT_URL}]: "
    read -r NEW_QDRANT_URL
    if [ -z "$NEW_QDRANT_URL" ]; then
        NEW_QDRANT_URL="$CURRENT_QDRANT_URL"
    fi

    echo -ne "Enter Qdrant API Key (leave blank for none/local) [${CURRENT_QDRANT_KEY:-none}]: "
    read -r NEW_QDRANT_KEY
    if [ -z "$NEW_QDRANT_KEY" ] && [ "$NEW_QDRANT_KEY" != "" ]; then
        # If user pressed enter, keep current key
        NEW_QDRANT_KEY="$CURRENT_QDRANT_KEY"
    fi

    # Update in .env using Python to avoid sed platform issues
    export NEW_QDRANT_URL_ENV="$NEW_QDRANT_URL"
    export NEW_QDRANT_KEY_ENV="$NEW_QDRANT_KEY"
    python3 -c "
import os
path = '$ENV_FILE'
content = open(path).read().splitlines()
for i, line in enumerate(content):
    if line.startswith('QDRANT_URL='):
        content[i] = f'QDRANT_URL={os.environ[\"NEW_QDRANT_URL_ENV\"]}'
    elif line.startswith('QDRANT_API_KEY='):
        content[i] = f'QDRANT_API_KEY={os.environ[\"NEW_QDRANT_KEY_ENV\"]}'
open(path, 'w').write('\n'.join(content) + '\n')
"
    echo -e "${GREEN}✓ Qdrant Connection Settings updated successfully.${NC}"
}

# Setup services (Docker & Qdrant)
setup_services() {
    print_header "External Services (Qdrant & Docker)"

    # Check if Docker is available
    if ! command -v docker &>/dev/null; then
        echo -e "${YELLOW}⚠️  Docker was not found in your system PATH.${NC}"
        echo -e "   The retrieval layer uses Qdrant, which runs inside a Docker container."
        echo -e "   We can fall back to ${BOLD}Stateless Mode${NC} (disabling Qdrant & Reranker in .env)."
        echo -ne "${BOLD}Do you want to run in Stateless Mode instead? (y/n) [n]:${NC} "
        read -r STATELESS_OPT
        if [[ "$STATELESS_OPT" =~ ^[Yy]$ ]]; then
            disable_qdrant_and_reranker
        else
            echo -e "${RED}❌ Please install Docker and start it to continue with Qdrant setup.${NC}"
            echo -e "   Or restart this script and opt for Stateless Mode."
            exit 1
        fi
        return
    fi

    # Check if Docker Daemon is running
    if ! docker info &>/dev/null; then
        echo -e "${YELLOW}⚠️  Docker is installed but the Docker Daemon is NOT running.${NC}"
        echo -e "   Please start Docker Desktop or the systemd Docker service."
        echo -ne "${BOLD}Would you like to fallback to Stateless Mode for now? (y/n) [n]:${NC} "
        read -r STATELESS_OPT
        if [[ "$STATELESS_OPT" =~ ^[Yy]$ ]]; then
            disable_qdrant_and_reranker
        else
            echo -e "${RED}❌ Docker daemon is required for local Qdrant. Start Docker and try again.${NC}"
            exit 1
        fi
        return
    fi

    echo -e "Docker daemon is ${GREEN}running${NC}."

    # Check if Qdrant container is already running
    RUNNING_CONTAINER=$(docker ps --filter "name=qdrant" --filter "status=running" --format "{{.Names}}")
    PORT_CHECK=$(docker ps --filter "publish=6333" --format "{{.Names}}")

    if [ -n "$RUNNING_CONTAINER" ]; then
        echo -e "${GREEN}✓ Qdrant container is already running ($RUNNING_CONTAINER).${NC}"
        enable_qdrant_and_reranker
    elif [ -n "$PORT_CHECK" ]; then
        echo -e "${GREEN}✓ Another container ($PORT_CHECK) is already running on port 6333.${NC}"
        enable_qdrant_and_reranker
    else
        # Check if qdrant-closed-loop container exists but is stopped
        EXISTING_CONTAINER=$(docker ps -a --filter "name=qdrant-closed-loop" --format "{{.Names}}")
        if [ -n "$EXISTING_CONTAINER" ]; then
            echo -e "Found existing stopped container '${BOLD}qdrant-closed-loop${NC}'. Starting it..."
            docker start qdrant-closed-loop >/dev/null
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Started existing Qdrant container.${NC}"
                enable_qdrant_and_reranker
            else
                echo -e "${RED}❌ Failed to start existing Qdrant container.${NC}"
                exit 1
            fi
        else
            # Create and launch new container
            echo -e "Launching new Qdrant vector database container on port 6333..."
            docker run -d --name qdrant-closed-loop -p 6333:6333 qdrant/qdrant >/dev/null
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Successfully started Qdrant container (qdrant-closed-loop).${NC}"
                enable_qdrant_and_reranker
            else
                echo -e "${RED}❌ Failed to start Qdrant container.${NC}"
                exit 1
            fi
        fi
    fi

    # Verify connection to Qdrant
    echo -e "Verifying Qdrant connectivity..."
    sleep 2 # Give it a brief moment
    QDRANT_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:6333/ || echo "failed")
    if [ "$QDRANT_HEALTH" = "200" ]; then
        echo -e "${GREEN}✓ Verified Qdrant is healthy & responding on http://localhost:6333${NC}"
    else
        echo -e "${YELLOW}⚠️  Qdrant container is active but port 6333 is not responding yet.${NC}"
        echo -e "   It might still be initializing. This is usually fine."
    fi
}

disable_qdrant_and_reranker() {
    python3 -c "
path = '$ENV_FILE'
content = open(path).read().splitlines()
for i, line in enumerate(content):
    if line.startswith('USE_QDRANT='):
        content[i] = 'USE_QDRANT=false'
    elif line.startswith('USE_RERANKER='):
        content[i] = 'USE_RERANKER=false'
open(path, 'w').write('\n'.join(content) + '\n')
"
    echo -e "${YELLOW}✓ Stateless mode enabled. Qdrant and Reranker turned OFF in .env.${NC}"
}

enable_qdrant_and_reranker() {
    python3 -c "
path = '$ENV_FILE'
content = open(path).read().splitlines()
for i, line in enumerate(content):
    if line.startswith('USE_QDRANT='):
        content[i] = 'USE_QDRANT=true'
    elif line.startswith('USE_RERANKER='):
        content[i] = 'USE_RERANKER=true'
open(path, 'w').write('\n'.join(content) + '\n')
"
    echo -e "${GREEN}✓ Rich retrieval mode enabled. Qdrant and Reranker turned ON in .env.${NC}"
}

# Status Check Utility
show_status() {
    print_banner
    print_header "System Status Overview"

    # 1. Virtual Env
    if [ -d "$VENV_DIR" ]; then
        echo -e "Python Virtualenv:  ${GREEN}✓ Installed (.venv)${NC}"
    else
        echo -e "Python Virtualenv:  ${RED}✗ Not found${NC}"
    fi

    # 2. .env Configuration
    if [ -f "$ENV_FILE" ]; then
        KEY_VAL=$(grep "REGOLO_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        if [ -n "$KEY_VAL" ] && [ "$KEY_VAL" != "your_api_key_here" ]; then
            # Mask key for display
            MASKED_KEY="${KEY_VAL:0:4}...${KEY_VAL: -4}"
            echo -e "API Configuration:  ${GREEN}✓ API Key set (${MASKED_KEY})${NC}"
        else
            echo -e "API Configuration:  ${RED}✗ API Key not set / using default placeholder${NC}"
        fi
        
        QDRANT_MODE=$(grep "USE_QDRANT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        echo -e "Configured Mode:    ${BOLD}${CYAN}$( [ "$QDRANT_MODE" = "true" ] && echo "Rich Retrieval (Qdrant ON)" || echo "Stateless (Qdrant OFF)" )${NC}"
    else
        echo -e "API Configuration:  ${RED}✗ .env file not found${NC}"
    fi

    # 3. Docker status
    if command -v docker &>/dev/null; then
        if docker info &>/dev/null; then
            echo -e "Docker Daemon:      ${GREEN}✓ Running${NC}"
        else
            echo -e "Docker Daemon:      ${YELLOW}⚠️  Installed but Stopped${NC}"
        fi
    else
        echo -e "Docker Daemon:      ${RED}✗ Not installed${NC}"
    fi

    # 4. Qdrant service status
    QDRANT_ALIVE="failed"
    if command -v curl &>/dev/null; then
        QDRANT_ALIVE=$(curl -s --connect-timeout 2 -o /dev/null -w "%{http_code}" http://localhost:6333/ 2>/dev/null || echo "failed")
    fi
    if [ "$QDRANT_ALIVE" = "200" ]; then
        echo -e "Qdrant DB Service:  ${GREEN}✓ Responsive (http://localhost:6333)${NC}"
    else
        # Check container presence
        if command -v docker &>/dev/null && docker info &>/dev/null; then
            CONTAINER_STATUS=$(docker ps --filter "name=qdrant" --format "{{.Status}}")
            if [ -n "$CONTAINER_STATUS" ]; then
                echo -e "Qdrant DB Service:  ${YELLOW}⚠️  Container is active ($CONTAINER_STATUS) but not responding yet.${NC}"
            else
                echo -e "Qdrant DB Service:  ${RED}✗ Offline / Not started${NC}"
            fi
        else
            echo -e "Qdrant DB Service:  ${RED}✗ Offline${NC}"
        fi
    fi
    echo ""
}

# Main workflow selector
run_menu() {
    while true; do
        print_banner
        echo -e " ${BOLD}Please select an option:${NC}"
        echo " 1) Complete setup (Python, dependencies, .env, services)"
        echo " 2) Start Closed-Loop Code Reviewer (main.py)"
        echo " 3) Check services status"
        echo " 4) Exit"
        echo ""
        echo -ne "${BOLD}Option [1-4]:${NC} "
        read -r OPTION

        case $OPTION in
            1)
                setup_python
                setup_env_file
                setup_services
                echo -e "\n${GREEN}🎉 Setup finished! You are ready to launch Regolo Closed-Loop.🎉${NC}"
                echo -ne "\nPress Enter to return to menu..."
                read -r
                ;;
            2)
                launch_project
                ;;
            3)
                show_status
                echo -ne "Press Enter to return to menu..."
                read -r
                ;;
            4)
                echo -e "\n${BOLD}Thank you for choosing Regolo.ai! Have a great review experience!${NC}"
                exit 0
                ;;
            *)
                # Default to setup if empty/invalid
                setup_python
                setup_env_file
                setup_services
                echo -e "\n${GREEN}🎉 Setup finished! You are ready to launch Regolo Closed-Loop.🎉${NC}"
                echo -ne "\nPress Enter to return to menu..."
                read -r
                ;;
        esac
    done
}

launch_project() {
    # Check if virtualenv is setup
    if [ ! -d "$VENV_DIR" ] || [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}⚠️  Environment is not fully set up. Running quick setup first...${NC}"
        setup_python
        setup_env_file
    fi

    echo -e "\n${BOLD}${GREEN}🚀 Starting Regolo Closed-Loop Code Reviewer...${NC}\n"
    # Execute python within the virtualenv
    "$VENV_DIR/bin/python" "$MAIN_PY"
    exit_code=$?
    echo -e "\n${BOLD}Process exited with status ${exit_code}.${NC}"
    echo -ne "Press Enter to return to menu..."
    read -r
}

# Parse Command Line Arguments
if [ $# -gt 0 ]; then
    case $1 in
        setup)
            print_banner
            setup_python
            setup_env_file
            setup_services
            echo -e "\n${GREEN}🎉 Setup complete! Run './setup.sh run' to start.${NC}"
            ;;
        run|start)
            launch_project
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            print_banner
            echo "Usage:"
            echo "  ./setup.sh         - Opens interactive terminal menu"
            echo "  ./setup.sh setup   - Installs python env, configures .env and starts Qdrant container"
            echo "  ./setup.sh run     - Runs the code reviewer pipeline"
            echo "  ./setup.sh status  - Displays current health and availability of all project services"
            echo "  ./setup.sh help    - Shows this help screen"
            echo ""
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            echo "Try: ./setup.sh help"
            exit 1
            ;;
    esac
else
    # Interactive mode
    run_menu
fi
