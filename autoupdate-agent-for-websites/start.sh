#!/bin/bash

# ==========================================
# Colors and formatting
# ==========================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ==========================================
# Cleanup function (Ctrl+C)
# ==========================================
cleanup() {
    printf "%b\n" "\n${YELLOW}========================================${NC}"
    printf "%b\n" "${RED}${BOLD}[INFO] Shutting down local processes...${NC}"
    kill $(jobs -p) 2>/dev/null
    
    printf "%b\n" "${CYAN}[INFO] Stopping Chroma DB on Docker...${NC}"
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.chroma.yml down
    elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
        docker compose -f docker-compose.chroma.yml down
    fi
    
    printf "%b\n" "${GREEN}All services (backend, frontend, and Chroma DB) have been successfully stopped.${NC}"
    printf "%b\n" "${YELLOW}========================================${NC}"
    exit
}

# Attach cleanup function to interrupt signals
trap cleanup SIGINT SIGTERM

printf "%b\n" "${CYAN}${BOLD}"
cat << "EOF"
    ___         __        __  __          __      __    
   /   | __  __/ /_____  / / / /___  ____/ /___ _/ /____
  / /| |/ / / / __/ __ \/ / / / __ \/ __  / __ `/ __/ _ \
 / ___ / /_/ / /_/ /_/ / /_/ / /_/ / /_/ / /_/ / /_/  __/
/_/  |_\__,_/\__/\____/\____/ .___/\__,_/\__,_/\__/\___/
                           /_/                          
    ___                    __                           
   /   | ____ ____  ____  / /_                          
  / /| |/ __ `/ _ \/ __ \/ __/                          
 / ___ / /_/ /  __/ / / / /_                            
/_/  |_\__, /\___/_/ /_/\__/                            
      /____/                                            
EOF
printf "%b\n" "${NC}"
printf "%b\n" "${BLUE}======================================================${NC}"
printf "%b\n" "${BOLD} Global Services Startup: AutoUpdate Agent${NC}"
printf "%b\n" "${BLUE}======================================================\n${NC}"

# ==========================================
# 1. Setup Python Virtual Environment
# ==========================================
printf "%b\n" "${CYAN}[1/4] Setting up Python virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    printf "%b\n" "${YELLOW}      Virtual environment not found. Creating .venv...${NC}"
    python3 -m venv .venv
fi

printf "%b\n" "${YELLOW}      Activating virtual environment and installing dependencies...${NC}"
source .venv/bin/activate
python3 -m pip install -r requirements.txt --quiet
printf "%b\n" "${GREEN}      Virtual environment ready and dependencies installed.${NC}"
echo ""

# ==========================================
# 2. Verify and Start Chroma DB
# ==========================================
printf "%b\n" "${CYAN}[2/5] Verifying and starting Chroma DB (port 8000)...${NC}"

# Create external volume for Chroma DB if it doesn't exist
if [ ! -d "./chroma_db_data" ]; then
    printf "%b\n" "${YELLOW}      External volume 'chroma_db_data' not found. Creating...${NC}"
    mkdir -p ./chroma_db_data
    printf "%b\n" "${GREEN}      External volume created successfully.${NC}"
fi

if ! curl -s http://localhost:8000/api/v1/heartbeat > /dev/null; then
    printf "%b\n" "${YELLOW}      Chroma DB is not responding. Starting container via Docker...${NC}"
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.chroma.yml up -d
    elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
        docker compose -f docker-compose.chroma.yml up -d
    else
        printf "%b\n" "${RED}[ERROR] Docker or Docker Compose not found. Cannot start Chroma DB.${NC}"
        exit 1
    fi
    
    # Wait for Chroma API to be ready
    printf "%b\n" "${YELLOW}      Waiting for Chroma DB API to be ready...${NC}"
    for i in {1..15}; do
        if curl -s http://localhost:8000/api/v1/heartbeat > /dev/null; then
            printf "%b\n" "${GREEN}      Chroma DB is now online and ready!${NC}"
            break
        fi
        sleep 1
        if [ $i -eq 15 ]; then
            printf "%b\n" "${RED}[ERROR] Timeout: Chroma DB failed to start properly.${NC}"
            exit 1
        fi
    done
else
    printf "%b\n" "${GREEN}      Chroma DB is already up and running.${NC}"
fi
echo ""

# ==========================================
# 3. Knowledge Base Initialization
# ==========================================
printf "%b\n" "${CYAN}[3/5] Initializing Knowledge Base...${NC}"

# Get AUTO_UPDATE_HOURS from .env if available
UPDATE_HOURS=24
if [ -f ".env" ]; then
    ENV_HOURS=$(grep -E '^AUTO_UPDATE_HOURS=' .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
    if [ -n "$ENV_HOURS" ]; then
        UPDATE_HOURS=$ENV_HOURS
    fi
fi

SKIP_SCRAPE=false
# Use python to calculate how many hours ago the log file was updated
LAST_UPDATE_HOURS=$(python3 -c "import os, time; print(int((time.time() - os.path.getmtime('content_generator_log.txt'))/3600)) if os.path.exists('content_generator_log.txt') else print(999999)")

if [ "$LAST_UPDATE_HOURS" -lt "$UPDATE_HOURS" ]; then
    if [ "$LAST_UPDATE_HOURS" -eq 0 ]; then
        LAST_UPDATE_MSG="less than an hour ago"
    else
        LAST_UPDATE_MSG="$LAST_UPDATE_HOURS hours ago"
    fi
    printf "%b\n" "${YELLOW}      Knowledge base was already updated ${LAST_UPDATE_MSG} (threshold is ${UPDATE_HOURS}h).${NC}"
    printf "%b" "${YELLOW}      Do you want to force a new scrape anyway? [y/N]: ${NC}"
    read FORCE_SCRAPE
    if [[ ! "$FORCE_SCRAPE" =~ ^[Yy]$ ]]; then
        SKIP_SCRAPE=true
        printf "%b\n" "${GREEN}      Skipping scraping. Using existing Chroma DB data.${NC}"
    fi
fi

if [ "$SKIP_SCRAPE" = false ]; then
    # Ask for the sitemap URL
    DEFAULT_URL="https://regolo.ai/sitemap_index.xml"
    if [ -f ".env" ]; then
        ENV_URL=$(grep -E '^KNOWLEDGE_BASE_URL=' .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
        if [ -n "$ENV_URL" ]; then
            DEFAULT_URL=$ENV_URL
        fi
    fi
    printf "%b" "${YELLOW}      Enter the sitemap URL to scan [Default: ${DEFAULT_URL}]: ${NC}"
    read USER_URL
    export KNOWLEDGE_BASE_URL="${USER_URL:-$DEFAULT_URL}"

    printf "%b\n" "${YELLOW}      Running content generator to scrape ${KNOWLEDGE_BASE_URL} and populate Chroma DB...${NC}"
    source .venv/bin/activate
    python3 content_generator.py
    printf "%b\n" "${GREEN}      Knowledge Base populated successfully.${NC}"
fi

# Verify if Chroma DB has data
printf "%b\n" "${YELLOW}      Checking if Chroma DB contains data...${NC}"
DB_COUNT=$(python3 -c "from chroma_client import get_chroma_http_client; client = get_chroma_http_client(); col = client.get_or_create_collection('autoupdate-agent'); print(col.count())" 2>/dev/null || echo "0")

if [ "$DB_COUNT" -eq 0 ]; then
    printf "%b\n" "${RED}[ERROR] Chroma DB is empty! The chat will not work properly without data.${NC}"
    printf "%b\n" "${YELLOW}      Please restart the script and force a scrape, or check content_generator_log.txt for errors.${NC}"
    exit 1
else
    printf "%b\n" "${GREEN}      Chroma DB is ready and contains ${DB_COUNT} documents.${NC}"
fi
echo ""

# ==========================================
# 4. Start FastAPI Backend
# ==========================================
printf "%b\n" "${CYAN}[4/5] Starting Backend (FastAPI on port 8080)...${NC}"
source .venv/bin/activate
# Run FastAPI in the background
python3 app.py &

printf "%b\n" "${YELLOW}      Waiting for backend to download/load embeddings and start...${NC}"
# Wait until the backend API is responsive (model loaded)
while ! curl -s http://localhost:8080/docs > /dev/null; do
    sleep 2
done
printf "%b\n" "${GREEN}      Python Backend started and model loaded successfully!${NC}"
echo ""

# ==========================================
# 5. Start Frontend (React Widget)
# ==========================================
printf "%b\n" "${CYAN}[5/5] Building React Widget and starting Static Server (port 3001)...${NC}"
cd autoupdate-agent-ui || exit
printf "%b\n" "${YELLOW}      Running npm install...${NC}"
npm install --silent
printf "%b\n" "${YELLOW}      Running npm run build...${NC}"
npm run build --silent
python3 -m http.server 3001 > /dev/null 2>&1 &
cd ..
printf "%b\n" "${GREEN}      Frontend compiled and served in background.${NC}"
echo ""

# ==========================================
# Summary
# ==========================================
printf "%b\n" "${BLUE}======================================================${NC}"
printf "%b\n" "${GREEN}${BOLD} ✓ ALL SERVICES ARE ACTIVE!${NC}"
printf "%b\n" "${BLUE}======================================================${NC}"
printf "%b\n" " 🗄️  ${BOLD}Chroma DB:${NC}    http://localhost:8000"
printf "%b\n" " 🚀 ${BOLD}Backend API:${NC}  http://localhost:8080"
printf "%b\n" " 💬 ${BOLD}Chat Embed:${NC}   http://localhost:3001/test-embed.html"
echo ""
printf "%b\n" "${YELLOW} Press [Ctrl+C] at any time to shut down the application.${NC}"
printf "%b\n" "${BLUE}======================================================${NC}"

# Wait for background processes to finish or user to press Ctrl+C
wait
