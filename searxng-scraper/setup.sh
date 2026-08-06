#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_banner() {
    clear
    echo -e "${GREEN}"
    echo "  ██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗ "
    echo "  ██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗"
    echo "  ██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║"
    echo "  ██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║"
    echo "  ██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝"
    echo "  ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ "
    echo -e "${NC}"
}

print_menu() {
    echo -e "\n${YELLOW}Please select an option:${NC}"
    echo "  [1] Setup environment (SearXNG container, venv, dependencies)"
    echo "  [2] Run demo query (default: 'regolo.ai')"
    echo "  [3] Run interactive custom search query"
    echo "  [0] Exit"
    echo -ne "\n${GREEN}Choice [0-3]: ${NC}"
}

setup_environment() {
    echo -e "${GREEN}[SETUP] Starting environment setup...${NC}"
    
    echo -e "${YELLOW}[SETUP] Checking existing SearXNG container / port 8080...${NC}"
    containers=$(docker ps -a -q --filter "ancestor=searxng/searxng:latest" --filter "ancestor=searxng/searxng" --filter "name=searxng")
    if [ -n "$containers" ]; then
        echo -e "${YELLOW}[SETUP] Removing existing SearXNG containers...${NC}"
        docker rm -f $containers 2>/dev/null || true
    fi
    port_container=$(docker ps -a -q --filter "publish=8080")
    if [ -n "$port_container" ]; then
        echo -e "${YELLOW}[SETUP] Freeing port 8080...${NC}"
        docker rm -f $port_container 2>/dev/null || true
    fi

    echo -e "${YELLOW}[SETUP] Pulling SearXNG Docker image...${NC}"
    docker pull searxng/searxng:latest
    
    echo -e "${YELLOW}[SETUP] Starting SearXNG container...${NC}"
    DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    docker run -d --name searxng -p 8080:8080 -v "$DIR/searxng-settings.yml:/etc/searxng/settings.yml:ro" searxng/searxng:latest
    
    echo -e "${YELLOW}[SETUP] Waiting for SearXNG to be ready...${NC}"
    for i in {1..15}; do
        if [ "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/)" = "200" ]; then
            echo -e "${GREEN}[SETUP] SearXNG is ready!${NC}"
            break
        fi
        sleep 1
    done
    
    echo -e "${YELLOW}[SETUP] Creating Python virtual environment...${NC}"
    python3 -m venv .venv
    
    echo -e "${YELLOW}[SETUP] Activating virtual environment and installing dependencies...${NC}"
    source .venv/bin/activate
    python3 -m pip install --upgrade pip
    python3 -m pip install setuptools wheel
    if [ -f "requirements.txt" ]; then
        python3 -m pip install -r requirements.txt
    fi
    python3 -m pip install -e .
    
    echo -e "${GREEN}[SETUP] Environment setup complete! SearXNG running on http://localhost:8080${NC}"
    read -p "Press enter to continue..."
}

run_demo() {
    echo -e "${GREEN}[DEMO] Running application with demo query...${NC}"
    source .venv/bin/activate
    export PYTHONPATH=src
    export SEARXNG_URL="${SEARXNG_URL:-http://localhost:8080}"
    if [ -f "src/regolo_private_search/app.py" ]; then
        python src/regolo_private_search/app.py --query "EU AI Act compliance"
    elif [ -f "app.py" ]; then
        python app.py --query "EU AI Act compliance"
    else
        echo -e "${RED}[ERROR] app.py not found.${NC}"
    fi
}

run_app() {
    echo -e "${GREEN}[APP] Interactive Search via SearXNG${NC}"
    echo -ne "${YELLOW}Enter your search query: ${NC}"
    read -r user_query
    if [ -z "$user_query" ]; then
        user_query="EU AI Act compliance"
    fi
    source .venv/bin/activate
    export PYTHONPATH=src
    export SEARXNG_URL="${SEARXNG_URL:-http://localhost:8080}"
    if [ -f "src/regolo_private_search/app.py" ]; then
        python src/regolo_private_search/app.py --query "$user_query"
    elif [ -f "app.py" ]; then
        python app.py --query "$user_query"
    else
        echo -e "${RED}[ERROR] app.py not found.${NC}"
    fi
}

print_banner
while true; do
    print_menu
    read -r choice
    
    case $choice in
        1)
            setup_environment
            print_banner
            ;;
        2)
            run_demo
            read -p "Press enter to continue..."
            print_banner
            ;;
        3)
            run_app
            read -p "Press enter to continue..."
            print_banner
            ;;
        0)
            echo -e "${GREEN}Exiting...${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option. Please try again.${NC}"
            ;;
    esac
done