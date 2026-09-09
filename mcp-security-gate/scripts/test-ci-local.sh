#!/usr/bin/env bash
# REGOLO MCP Security Gate - Local GitHub Workflow Runner
# Replicates the exact steps executed by .github/workflows/mcp-gate.yml

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

# Colors
C_GREEN="\033[38;5;46m"
C_RED="\033[38;5;196m"
C_CYAN="\033[38;5;51m"
C_DIM="\033[2m"
C_RESET="\033[0m"

echo -e "\n${C_GREEN}======================================================================${C_RESET}"
echo -e "${C_GREEN} [REGOLO] LOCAL GITHUB ACTIONS CI RUNNER (.github/workflows/mcp-gate.yml) ${C_RESET}"
echo -e "${C_GREEN}======================================================================${C_RESET}\n"

# Mode: Docker container vs Native host
if [[ "$1" == "--docker" ]]; then
    if ! command -v docker &> /dev/null; then
        echo -e "${C_RED}Error: Docker is not installed or not in PATH.${C_RESET}"
        exit 1
    fi
    echo -e "${C_CYAN}[MODE: DOCKER CONTAINER]${C_RESET} Executing inside isolated python:3.11-slim (matching GitHub runner)..."
    docker run --rm -v "$DIR":/app -w /app python:3.11-slim bash -c "
        set -e
        echo -e '${C_DIM}>>> Step 1: Install Dependencies...${C_RESET}'
        pip install --quiet --upgrade pip
        pip install --quiet -r requirements.txt

        echo -e '${C_DIM}>>> Step 2: Run Unit Tests...${C_RESET}'
        python3 -m unittest discover tests/

        echo -e '${C_DIM}>>> Step 3: Full Repository Scan (Tracked files, excluding .gitignore)...${C_RESET}'
        TRACKED_FILES=\$(git ls-files | grep -E '\.(py|js|ts|json)$' || true)
        for FILE in \$TRACKED_FILES; do
            if [[ \"\$FILE\" =~ ^(gate|tests)/ ]] || [[ \"\$FILE\" == \"mcp-lock.json\" ]] || [[ \"\$FILE\" == \"package.json\" ]]; then
                continue
            fi
            if [[ \"\$FILE\" =~ demo/(poisoned_server|rugpull_server/v2|sample_claude_desktop_config) ]]; then
                continue
            fi
            if grep -qE '(tools/list|@mcp\.tool|server\.tool|mcpServers|inputSchema)' \"\$FILE\" 2>/dev/null; then
                echo \"==> Auditing tracked MCP definition: \$FILE\"
                python3 -m gate.gate_cli scan \"\$FILE\"
            fi
        done

        echo -e '${C_DIM}>>> Step 4: Verify Against Immutable mcp-lock.json...${C_RESET}'
        python3 -m gate.gate_cli lock --out mcp-lock.json
        git diff --exit-code mcp-lock.json || (echo -e '${C_RED}ERROR: mcp-lock.json has uncommitted drift!${C_RESET}' && exit 1)

        echo -e '${C_DIM}>>> Step 5: Validate Self-Defense against Poisoned Server...${C_RESET}'
        if python3 -m gate.gate_cli scan demo/poisoned_server/server.py; then
            echo -e '${C_RED}ERROR: Poisoned MCP server was NOT blocked!${C_RESET}'
            exit 1
        else
            echo -e '${C_GREEN}SUCCESS: Poisoned MCP server successfully blocked by REGOLO Security Gate.${C_RESET}'
        fi
    "
    echo -e "\n${C_GREEN}======================================================================${C_RESET}"
    echo -e "${C_GREEN} [SUCCESS] LOCAL CI RUN (DOCKER) COMPLETED: WORKFLOW PASSES! ${C_RESET}"
    echo -e "${C_GREEN}======================================================================${C_RESET}\n"
    exit 0
fi

# Native host mode
if [ ! -d ".venv" ]; then
    echo -e "${C_DIM}Creating isolated virtualenv at .venv...${C_RESET}"
    python3 -m venv .venv
fi

PYTHON_BIN=".venv/bin/python3"
PIP_BIN=".venv/bin/pip"

echo -e "${C_CYAN}[MODE: NATIVE HOST]${C_RESET} Executing with $PYTHON_BIN..."

echo -e "\n${C_CYAN}>>> Step 1: Install / Verify Dependencies${C_RESET}"
$PIP_BIN install --quiet --upgrade pip
$PIP_BIN install --quiet -r requirements.txt
echo -e "${C_GREEN}Dependencies verified.${C_RESET}"

echo -e "\n${C_CYAN}>>> Step 2: Run Security Engine Unit Tests${C_RESET}"
$PYTHON_BIN -m unittest discover tests/

echo -e "\n${C_CYAN}>>> Step 3: Full Repository Scan (Tracked files, excluding .gitignore)${C_RESET}"
TRACKED_FILES=$(git ls-files 2>/dev/null | grep -E '\.(py|js|ts|json)$' || true)
if [ -z "$TRACKED_FILES" ]; then
    # Fallback if not inside a git checkout
    TRACKED_FILES="demo/safe_server/server.py demo/rugpull_server/v1/server.py demo/nodejs_server/index.js"
fi

for FILE in $TRACKED_FILES; do
    if [[ "$FILE" =~ ^(gate|tests)/ ]] || [[ "$FILE" == "mcp-lock.json" ]] || [[ "$FILE" == "package.json" ]]; then
        continue
    fi
    if [[ "$FILE" =~ demo/(poisoned_server|rugpull_server/v2|sample_claude_desktop_config) ]]; then
        continue
    fi
    if grep -qE '(tools/list|@mcp\.tool|server\.tool|mcpServers|inputSchema)' "$FILE" 2>/dev/null; then
        echo -e "==> Auditing tracked MCP definition: $FILE"
        $PYTHON_BIN -m gate.gate_cli scan "$FILE"
    fi
done

echo -e "\n${C_CYAN}>>> Step 4: Verify Against Immutable mcp-lock.json${C_RESET}"
$PYTHON_BIN -m gate.gate_cli lock --out mcp-lock.json

echo -e "\n${C_CYAN}>>> Step 5: Validate Self-Defense against Poisoned Server (Must Block)${C_RESET}"
if $PYTHON_BIN -m gate.gate_cli scan demo/poisoned_server/server.py; then
    echo -e "${C_RED}ERROR: Poisoned MCP server was NOT blocked by REGOLO Security Gate!${C_RESET}"
    exit 1
else
    echo -e "\n${C_GREEN}SUCCESS: Poisoned MCP server was blocked with exit code 1 as expected.${C_RESET}"
fi

echo -e "\n${C_GREEN}======================================================================${C_RESET}"
echo -e "${C_GREEN} [SUCCESS] LOCAL CI RUN COMPLETED: WORKFLOW PASSES! ${C_RESET}"
echo -e "${C_GREEN}======================================================================${C_RESET}\n"
