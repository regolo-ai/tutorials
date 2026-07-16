#!/usr/bin/env bash

# ==============================================================================
#  Regolo.ai - Project Setup & Management CLI
# ==============================================================================
#  A branded, automated CLI tool to set up the environment, configure API keys,
#  manage Docker services, and launch the Closed-Loop Code Reviewer.
# ==============================================================================

set -euo pipefail

# Text formatting helper constants
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Base directory setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"
VENV_DIR="${ROOT_DIR}/.venv"
REQUIREMENTS_FILE="${ROOT_DIR}/requirements.txt"
MAIN_PY="${ROOT_DIR}/agent.py"
EVAL_PY="${ROOT_DIR}/evaluation.py"

# Branded Banner
print_banner() {
    clear
    echo -e "${GREEN}"
    echo "  ██████╗ ███████╗ ██████╗  ██████╗ ██╗       ██████╗        █████╗ ██╗"
    echo "  ██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║      ██╔═══██╗      ██╔══██╗██║"
    echo "  ██████╔╝█████╗  ██║  ███╗██║   ██║██║      ██║   ██║      ███████║██║"
    echo "  ██╔══██╗██╔══╝  ██║   ██║██║   ██║██║      ██║   ██║.     ██╔══██║██║"
    echo "  ██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝ ██║   ██║  ██║██║"
    echo "  ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝  ══╝   ╚═╝  ╚═╝╚═╝"
    echo -e "${NC}"
    echo -e " ${BOLD}⚡ CLOSED-LOOP ENVIRONMENT MANAGER ⚡${NC}"
    echo -e " =============================================================================="
}

# Print section headers nicely
print_header() {
    echo -e "\n${BOLD}${CYAN}▶ $1${NC}"
    echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
}

# Display menu
print_menu() {
    echo -e "\n${BOLD}────────────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${CYAN}Select an option:${NC}"
    echo -e "  ${GREEN}1${NC}) Set Environment"
    echo -e "  ${GREEN}2${NC} Check Services"
    echo -e "  ${GREEN}3${NC} Run Project"
    echo -e "  ${YELLOW}4${NC} Exit"
    echo -e "${BOLD}────────────────────────────────────────────────────────────────────────────${NC}"
}

# Setup environment
setup_env() {
    print_header "🔧 Environment Setup"

    # Create .env file if it doesn't exist
    if [[ ! -f "$ENV_FILE" ]]; then
        if [[ -f "$ENV_EXAMPLE" ]]; then
            echo -e "Creating .env file from template..."
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            echo -e "${GREEN}✓ Created .env file${NC}"
        else
            echo -e "${YELLOW}⚠ .env.example not found${NC}"
            echo -e "   Creating .env file with placeholder API key..."
            cat > "$ENV_FILE" <<EOF
OPENAI_API_KEY=your-api-key-here
EOF
            echo -e "${GREEN}✓ Created .env file with placeholder API key${NC}"
            echo -e "${YELLOW}  └─ Please edit .env and set your OPENAI_API_KEY${NC}"
        fi
    else
        echo -e "${GREEN}✓ .env file already exists${NC}"
    fi

    # Setup virtual environment
    if [[ ! -d "$VENV_DIR" ]]; then
        echo -e "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    else
        echo -e "${GREEN}✓ Virtual environment already exists${NC}"
    fi

    # Activate virtual environment and install dependencies
    echo -e "Installing dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r "$REQUIREMENTS_FILE"
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# Check services
check_services() {
    print_header "🔍 Service Diagnostics"

    local missing=0

    # Check Python
    if command -v python3 &>/dev/null; then
        echo -e "${GREEN}✓ Python 3 is available${NC}"
    else
        echo -e "${RED}✗ Python 3 is not installed${NC}"
        ((missing++))
    fi

    # Check virtual environment
    if [[ -d "$VENV_DIR" ]]; then
        echo -e "${GREEN}✓ Virtual environment exists${NC}"
        echo -e "   Active Python version:\n"
        source "$VENV_DIR/bin/activate"
        python --version
        deactivate
    else
        echo -e "${YELLOW}⚠ Virtual environment not found${NC}"
        echo -e "   Run '1) Set Environment' to create it"
        ((missing++))
    fi

    # Check Docker
    if command -v docker &>/dev/null; then
        echo -e "${GREEN}✓ Docker is available${NC}"
    else
        echo -e "${YELLOW}⚠ Docker is not installed${NC}"
        ((missing++))
    fi

    # Check Qdrant
    if command -v qdrant &>/dev/null && pgrep -x qdrant > /dev/null; then
        echo -e "${GREEN}✓ Qdrant is running${NC}"
    else
        # Check if port 6333 is already in use (Qdrant might be running via docker compose or manually)
        if ss -tuln 2>/dev/null | grep -q ":6333" || lsof -ti:6333 2>/dev/null | grep -q .; then
            echo -e "${GREEN}✓ Qdrant appears to be accessible on port 6333${NC}"
        else
            echo -e "${YELLOW}⚠ Qdrant is not accessible on port 6333${NC}"
            echo -e "   The port is not allocated, checking alternatives..."
            
            # Try to start Qdrant
            echo -e "${CYAN}  Starting Qdrant with Docker...${NC}"
            
            # Remove any existing container to avoid port conflicts
            docker rm -f qdrant-local 2>/dev/null || true
            
            docker run -d \
              --name qdrant-local \
              -p 6333:6333 \
              -p 1230:1230 \
              qdrant/qdrant:latest
            
            sleep 2
            
            # Check if container is running
            if docker ps | grep -q "qdrant-local"; then
                echo -e "${GREEN}✓ Qdrant started successfully${NC}"
            else
                echo -e "${RED}✗ Failed to start Qdrant${NC}"
                echo -e "   Please ensure port 6333 is not in use"
                ((missing++))
            fi
        fi
    fi

    # Summary
    echo ""
    if [[ $missing -eq 0 ]]; then
        echo -e "${GREEN}All services are ready!${NC}"
    else
        echo -e "${YELLOW}$missing service(s) missing or not running${NC}"
    fi
}

# Run project
run_project() {
    print_header "🚀 Run Project"

    # Check if virtual environment exists and activate it
    if [[ ! -d "$VENV_DIR" ]]; then
        echo -e "${RED}✗ Virtual environment not found${NC}"
        echo -e "   Please run '1) Set Environment' first"
        return 1
    fi

    source "$VENV_DIR/bin/activate"

    # Check if .env exists
    if [[ ! -f "$ENV_FILE" ]]; then
        echo -e "${RED}✗ .env file not found${NC}"
        echo -e "   Please run '1) Set Environment' first"
        deactivate
        return 1
    fi

    echo -e "Starting ${BOLD}${GREEN}Regolo.ai Evaluation${NC}..."
    echo ""
    echo -e "${CYAN}============================================${NC}"
    
    # Change directory to ROOT_DIR to ensure relative paths work
    cd "$ROOT_DIR"

    # Run the evaluation
    python3 "$EVAL_PY"
    
    # Check exit code
    local rc=$?
    deactivate

    if [[ $rc -eq 0 ]]; then
        echo -e "\n${GREEN}✓ Agent completed successfully${NC}"
    else
        echo -e "\n${RED}✗ Agent exited with code $rc${NC}"
        return $rc
    fi
}

# Main menu
main() {
    print_banner

    while true; do
        print_menu

        read -rp "Enter your choice: " choice

        case $choice in
            1)
                setup_env
                ;;
            2)
                check_services
                ;;
            3)
                run_project
                ;;
            4|'')
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            *)
                echo -e "${YELLOW}Invalid option. Please try again.${NC}"
                ;;
        esac
    done
}

# Run main function
main
