#!/bin/bash
set -Eeuo pipefail

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ASCII Art Banner
show_banner() {
    clear
    echo -e "${CYAN}"
    cat << 'EOF'
██████╗ ███████╗ ██████╗ ██████╗ ██╗      ██████╗ 
██╔══██╗██╔════╝██╔════╝██╔════██╗██║     ██╔═══██╗
██████╔╝█████╗  ██║  ███╗██║   ███║██║     ██║   ██║
██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║
██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝
╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ 
EOF
    echo -e "${NC}"
}

# Print colored message
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[✓]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $*"; }
log_error() { echo -e "${RED}[✗]${NC} $*" >&2; }

# Check if command exists
command_exists() { command -v "$1" >/dev/null 2>&1; }

# Setup virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment..."
    cd "$PROJECT_ROOT"
    
    if [[ -d ".venv" ]]; then
        log_success "Virtual environment already exists"
    else
        python3 -m venv .venv
        log_success "Created virtual environment"
    fi
    
    source .venv/bin/activate
    log_success "Activated virtual environment"
}

# Install dependencies
install_deps() {
    log_info "Installing Python dependencies..."
    python3 -m pip install --quiet --break-system-packages --upgrade pip
    python3 -m pip install --quiet --break-system-packages -r requirements.txt
    log_success "Dependencies installed"
    
    # Check for knowledge_base module
    if [[ -f "knowledge_base.py" ]]; then
        log_success "Knowledge base module found"
    elif [[ -d "knowledge_base" ]]; then
        log_success "Knowledge base package found"
    else
        log_warning "knowledge_base module not found - creating stub"
        cat > knowledge_base.py << 'PYEOF'
from langchain_core.documents import Document

POLICY_DOCUMENTS = [
    Document(page_content="Activation rate = activated users / signups. Target: 40% minimum.", metadata={"source": "metrics_glossary.md"}),
    Document(page_content="Self-serve segment: acquired via paid channels. Monitored for funnel health.", metadata={"source": "metrics_glossary.md"}),
    Document(page_content="Sales-led segment: acquired via outbound sales. Higher SQL quality, longer sales cycle.", metadata={"source": "metrics_glossary.md"}),
]
PYEOF
        log_success "Created knowledge_base.py stub"
    fi
}

# Setup environment file
setup_env() {
    if [[ ! -f ".env" && -f ".env.example" ]]; then
        log_info "Creating .env from .env.example..."
        cp .env.example .env
        log_warning "Please edit .env and set your REGOLO_API_KEY"
    elif [[ -f ".env" ]]; then
        log_success ".env already configured"
    fi
}

# Check if Docker daemon is running, start Docker Desktop if on macOS
ensure_docker_running() {
    log_info "Checking Docker status..."
    if ! docker info >/dev/null 2>&1; then
        log_warning "Docker daemon is not running."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            log_info "Attempting to start Docker Desktop on macOS..."
            open -a Docker 2>/dev/null || open -a "Docker Desktop" 2>/dev/null || true
            
            log_info "Waiting for Docker daemon to start..."
            local count=0
            while ! docker info >/dev/null 2>&1; do
                sleep 2
                count=$((count + 1))
                if [ $count -gt 15 ]; then
                    log_error "Docker daemon failed to start. Please open Docker Desktop manually and try again."
                    return 1
                fi
            done
            log_success "Docker daemon is now running."
        else
            log_error "Please start the Docker service/daemon manually and try again."
            return 1
        fi
    fi
    return 0
}

# Start Qdrant service via Docker
start_qdrant() {
    log_info "Checking Qdrant service with Docker..."
    
    if ! command_exists docker; then
        log_error "Docker not found. Please install Docker first."
        return 1
    fi

    if ! ensure_docker_running; then
        return 1
    fi
    
    # Check if Qdrant container is running
    if docker ps --format '{{.Names}}' | grep -q '^qdrant$'; then
        log_success "Qdrant container already running"
    else
        # Check if Qdrant image exists
        if ! docker images --format '{{.Repository}}' | grep -q '^qdrant/qdrant$'; then
            log_info "Pulling Qdrant Docker image..."
            docker pull qdrant/qdrant:latest
            log_success "Qdrant image pulled"
        fi
        
        # Create data directory
        mkdir -p "$PROJECT_ROOT/.qdrant-storage"
        
        # Start Qdrant container
        log_info "Starting Qdrant container..."
        docker run -d \
            --name qdrant \
            -p 6333:6333 \
            -p 6334:6334 \
            -v "$PROJECT_ROOT/.qdrant-storage:/qdrant/storage" \
            --restart unless-stopped \
            qdrant/qdrant:latest
        
        sleep 3
        
        # Verify container is running
        if docker ps --format '{{.Names}}' | grep -q '^qdrant$'; then
            log_success "Qdrant container started on port 6333"
        else
            log_error "Failed to start Qdrant container"
            return 1
        fi
    fi

    # Automatically update or create .env with QDRANT_URL
    if [[ -f ".env" ]]; then
        if grep -q "QDRANT_URL=" .env; then
            # Update existing QDRANT_URL
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' 's|.*QDRANT_URL=.*|QDRANT_URL=http://localhost:6333|g' .env
            else
                sed -i 's|.*QDRANT_URL=.*|QDRANT_URL=http://localhost:6333|g' .env
            fi
        else
            # Append QDRANT_URL
            echo "QDRANT_URL=http://localhost:6333" >> .env
        fi
        log_success "Updated .env with QDRANT_URL=http://localhost:6333"
    elif [[ -f ".env.example" ]]; then
        cp .env.example .env
        if grep -q "QDRANT_URL=" .env; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' 's|.*QDRANT_URL=.*|QDRANT_URL=http://localhost:6333|g' .env
            else
                sed -i 's|.*QDRANT_URL=.*|QDRANT_URL=http://localhost:6333|g' .env
            fi
        else
            echo "QDRANT_URL=http://localhost:6333" >> .env
        fi
        log_success "Created .env from .env.example and configured QDRANT_URL"
    else
        cat > .env << 'ENVEOF'
REGOLO_API_KEY=replace_me
REGOLO_MODEL=gpt-oss-120b
QDRANT_PATH=.qdrant
QDRANT_URL=http://localhost:6333
ENVEOF
        log_success "Created new .env file with Qdrant configuration"
    fi
}

# Run tests
run_tests() {
    log_info "Running tests..."
    if [[ -f "test_app.py" ]]; then
        pytest test_app.py -v
        log_success "Tests passed"
    else
        log_warning "No test file found"
    fi
}

# Run the application
run_app() {
    log_info "Starting application..."
    if [[ -f "app.py" ]]; then
        log_info "Loading environment and launching app.py..."
        log_info "Connecting to Qdrant and LLM (Regolo API)... Please wait for the response..."
        echo ""
        python3 app.py
        echo ""
        log_success "Application execution finished."
    else
        log_error "app.py not found"
        exit 1
    fi
}

# Combined Setup Environment (venv, docker, dependencies, env)
setup_environment() {
    log_info "Starting Environment Setup..."
    setup_venv
    install_deps
    setup_env
    start_qdrant
}

# Main menu
show_menu() {
    echo -e "\n${BOLD}${WHITE}=== Regolo Setup Menu ===${NC}"
    echo ""
    echo -e "  ${CYAN}1)${NC} Setup Environment (venv, dependencies, .env, Docker Qdrant)"
    echo -e "  ${CYAN}2)${NC} Start Qdrant service"
    echo -e "  ${CYAN}3)${NC} Run tests"
    echo -e "  ${CYAN}4)${NC} Run application"
    echo -e "  ${CYAN}5)${NC} Exit"
    echo ""
}

# Main loop
main() {
    while true; do
        show_banner
        show_menu
        
        read -r -p $'\033[1;37mSelect option [1-5]:\033[0m ' choice
        
        case "$choice" in
            1)
                setup_environment
                ;;
            2)
                start_qdrant
                ;;
            3)
                setup_venv
                run_tests
                ;;
            4)
                setup_venv
                setup_env
                run_app
                ;;
            5)
                log_info "Exiting..."
                exit 0
                ;;
            *)
                log_error "Invalid option"
                ;;
        esac
        
        echo ""
        read -r -p $'\033[1;37mPress Enter to continue...\033[0m' _
    done
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}Interrupted. Exiting...${NC}"; exit 1' INT TERM

main "$@"