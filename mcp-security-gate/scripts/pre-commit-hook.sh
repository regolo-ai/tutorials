#!/usr/bin/env bash
# REGOLO MCP Security Gate - Git Pre-Commit Hook
# Inspects staged MCP server files and agent configs, skipping all .gitignore files.

set -e

# ANSI Colors
C_GREEN="\033[38;5;46m"
C_RED="\033[38;5;196m"
C_DIM="\033[2m"
C_RESET="\033[0m"

echo -e "${C_GREEN}[REGOLO GATE]${C_RESET} Inspecting staged files for MCP tool vulnerabilities..."

# git diff --cached only inspects staged files, automatically skipping any files ignored by .gitignore
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|js|ts|json)$' || true)

if [ -z "$STAGED_FILES" ]; then
    echo -e "${C_GREEN}[REGOLO GATE]${C_RESET} No MCP definitions or configs modified. Clean commit."
    exit 0
fi

# Locate gate engine
GATE_RUNNER=""
if python3 -m gate.gate_cli --help > /dev/null 2>&1; then
    GATE_RUNNER="python3 -m gate.gate_cli"
elif [ -d "$HOME/.regolo-mcp-gate" ]; then
    export PYTHONPATH="$HOME/.regolo-mcp-gate:$PYTHONPATH"
    GATE_RUNNER="python3 -m gate.gate_cli"
fi

for FILE in $STAGED_FILES; do
    # Skip lockfiles and tests
    if [[ "$FILE" == "mcp-lock.json" ]] || [[ "$FILE" =~ (tests/|\.test\.|\.spec\.) ]]; then
        continue
    fi

    # Check if file defines an MCP tool or agent configuration
    if grep -qE '(tools/list|@mcp\.tool|server\.tool|mcpServers|inputSchema)' "$FILE" 2>/dev/null; then
        echo -e "${C_GREEN}[MCP SECURITY GATE]${C_RESET} Auditing staged MCP definition: ${C_DIM}$FILE${C_RESET}"

        if [ -n "$GATE_RUNNER" ]; then
            if ! $GATE_RUNNER scan "$FILE" --json > /dev/null 2>&1; then
                echo -e "\n${C_RED}[COMMIT BLOCKED BY MCP SECURITY GATE]${C_RESET} Security injection or rug-pull found in $FILE:"
                $GATE_RUNNER scan "$FILE"
                exit 1
            fi
        else
            # Fast static regex check if gate engine is not yet in python path
            if grep -qiE '(ignore.*previous.*instructions|\[system.*override\]|silently.*read|~/\.ssh/id_rsa|os\.environ|process\.env)' "$FILE"; then
                echo -e "\n${C_RED}[COMMIT BLOCKED BY MCP SECURITY GATE]${C_RESET} Malicious instruction or credential target detected in $FILE!"
                grep -niE '(ignore.*previous.*instructions|\[system.*override\]|silently.*read|~/\.ssh/id_rsa|os\.environ|process\.env)' "$FILE"
                exit 1
            fi
        fi
    fi
done

echo -e "${C_GREEN}[REGOLO GATE PASSED]${C_RESET} All staged MCP tools verified safe."
exit 0
