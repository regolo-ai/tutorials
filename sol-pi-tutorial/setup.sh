#!/usr/bin/env bash
# ==============================================================================
#  ██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗ 
#  ██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗
#  ██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║
#  ██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║
#  ██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝
#  ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ 
#
#  SoL-Pi + Regolo Coding Agent Tutorial — Automated Environment Setup
# ==============================================================================

set -eo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ------------------------------------------------------------------------------
# Terminal Color & Styling Palette (REGOLO Green Theme)
# ------------------------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    G_BOLD="\033[1;38;5;82m"       # Bold Bright Regolo Green
    G_ACCENT="\033[38;5;48m"       # Mint Green Accent
    G_FOREST="\033[38;5;34m"       # Forest Green Border
    G_DIM="\033[38;5;29m"          # Dim Green
    C_WHITE="\033[1;97m"           # Crisp White
    C_GRAY="\033[38;5;246m"        # Slate Gray
    C_CYAN="\033[38;5;51m"         # Cyan
    C_YELLOW="\033[38;5;220m"      # Amber Warning
    C_RED="\033[38;5;196m"         # Error Red
    C_RESET="\033[0m"              # Reset
else
    G_BOLD=""
    G_ACCENT=""
    G_FOREST=""
    G_DIM=""
    C_WHITE=""
    C_GRAY=""
    C_CYAN=""
    C_YELLOW=""
    C_RED=""
    C_RESET=""
fi

# Cursor visibility helpers
show_cursor() { tput cnorm 2>/dev/null || true; }
hide_cursor() { tput civis 2>/dev/null || true; }
trap show_cursor EXIT INT TERM

# ------------------------------------------------------------------------------
# TUI Helper Functions
# ------------------------------------------------------------------------------
print_banner() {
    [ -t 1 ] && clear 2>/dev/null || true
    echo -e "${G_BOLD}"
    cat << 'EOF'
  ██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗ 
  ██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗
  ██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║
  ██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║
  ██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝
  ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ 
EOF
    echo -e "${C_RESET}"
    echo -e "  ${G_BOLD}⚡ R E G O L O  •  S o L - P i   B E N C H M A R K   S U I T E ⚡${C_RESET}"
    echo -e "  ${C_GRAY}Context Reduction & Paired Token Efficiency on the Pi Coding Agent${C_RESET}"
    echo -e "  ${G_FOREST}──────────────────────────────────────────────────────────────────────────${C_RESET}"
    echo -e "  ${C_GRAY}Target Directory :${C_RESET} ${C_WHITE}${PROJECT_DIR}${C_RESET}"
    echo -e "  ${C_GRAY}Architecture     :${C_RESET} ${C_WHITE}$(uname -s)/$(uname -m)${C_RESET} • ${C_GRAY}Date:${C_RESET} ${C_WHITE}$(date +'%Y-%m-%d %H:%M')${C_RESET}"
    echo -e "  ${G_FOREST}──────────────────────────────────────────────────────────────────────────${C_RESET}\n"
}

step_header() {
    local step_num="$1"
    local total_steps="$2"
    local title="$3"
    echo -e "  ${G_ACCENT}╭── [${step_num}/${total_steps}] ${C_WHITE}${title}${G_ACCENT} $(printf '─%.0s' {1..38})${C_RESET}"
}

step_footer() {
    echo -e "  ${G_ACCENT}╰────────────────────────────────────────────────────────────────────────${C_RESET}\n"
}

tui_success() {
    local msg="$1"
    echo -e "  ${G_ACCENT}│${C_RESET}  ${G_BOLD}[ ✔ ]${C_RESET} ${C_WHITE}${msg}${C_RESET}"
}

tui_info() {
    local msg="$1"
    echo -e "  ${G_ACCENT}│${C_RESET}  ${C_CYAN}[ ➜ ]${C_RESET} ${C_GRAY}${msg}${C_RESET}"
}

tui_warn() {
    local msg="$1"
    echo -e "  ${G_ACCENT}│${C_RESET}  ${C_YELLOW}[ ⚠ ]${C_RESET} ${C_YELLOW}${msg}${C_RESET}"
}

tui_error() {
    local msg="$1"
    echo -e "  ${G_ACCENT}│${C_RESET}  ${C_RED}[ ✖ ]${C_RESET} ${C_RED}${msg}${C_RESET}"
}

run_spinner() {
    local label="$1"
    shift
    local logfile
    logfile=$(mktemp)
    
    "$@" > "$logfile" 2>&1 &
    local pid=$!
    
    local spinchars=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
    local i=0
    
    hide_cursor
    while kill -0 "$pid" 2>/dev/null; do
        local spin="${spinchars[i % 10]}"
        printf "\r  ${G_ACCENT}│${C_RESET}  ${G_BOLD}%s${C_RESET} %s..." "$spin" "$label"
        i=$((i + 1))
        sleep 0.08
    done
    
    wait "$pid"
    local status=$?
    show_cursor
    
    if [ $status -eq 0 ]; then
        printf "\r  ${G_ACCENT}│${C_RESET}  ${G_BOLD}[ ✔ ]${C_RESET} %s\033[K\n" "$label"
        rm -f "$logfile"
        return 0
    else
        printf "\r  ${G_ACCENT}│${C_RESET}  ${C_RED}[ ✖ ]${C_RESET} %s ${C_RED}(failed)${C_RESET}\033[K\n" "$label"
        if [ -s "$logfile" ]; then
            echo -e "  ${G_ACCENT}│${C_RESET}     ${C_GRAY}Diagnostic log:${C_RESET}"
            tail -n 5 "$logfile" | while IFS= read -r line; do
                echo -e "  ${G_ACCENT}│${C_RESET}     ${C_RED}${line}${C_RESET}"
            done
        fi
        rm -f "$logfile"
        return $status
    fi
}

# ------------------------------------------------------------------------------
# MAIN SETUP SEQUENCE
# ------------------------------------------------------------------------------
print_banner

TOTAL_STEPS=8

# ==============================================================================
# Step 1: System Prerequisites
# ==============================================================================
step_header "1" "$TOTAL_STEPS" "System Prerequisites Verification"

# Check Python 3
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
        tui_success "Python ${PY_VER} detected (>= 3.10 required)"
    else
        tui_error "Python ${PY_VER} detected, but 3.10+ is required"
        exit 1
    fi
else
    tui_error "Python 3 is not installed"
    exit 1
fi

# Check Node.js
if command -v node >/dev/null 2>&1; then
    NODE_VER=$(node -v 2>/dev/null || echo "unknown")
    NODE_MAJOR=$(node -e "console.log(process.versions.node.split('.')[0])" 2>/dev/null || echo "0")
    if [ "$NODE_MAJOR" -ge 22 ]; then
        tui_success "Node.js ${NODE_VER} detected (>= 22.19 required for SoL-Pi)"
    else
        tui_warn "Node.js ${NODE_VER} detected. SoL-Pi recommends Node.js 22.19+"
    fi
else
    tui_error "Node.js is not installed (Node.js 22+ required for Pi)"
    exit 1
fi

# Check Git
if command -v git >/dev/null 2>&1; then
    GIT_VER=$(git --version | awk '{print $3}')
    tui_success "Git v${GIT_VER} detected"
else
    tui_error "Git is not installed"
    exit 1
fi

# Check Pi CLI
if command -v pi >/dev/null 2>&1; then
    PI_VER=$(pi --version 2>/dev/null || echo "detected")
    tui_success "Pi Coding Agent (${PI_VER}) available in PATH"
else
    tui_warn "Pi CLI not found in PATH."
    tui_info "Attempting global installation via npm..."
    if command -v npm >/dev/null 2>&1; then
        run_spinner "Installing @earendil-works/pi-coding-agent" npm install --global --ignore-scripts @earendil-works/pi-coding-agent@0.85.1 || {
            tui_error "Could not install Pi automatically. Please run: npm install -g @earendil-works/pi-coding-agent@0.85.1"
            exit 1
        }
    else
        tui_error "npm not found. Please install Pi manually."
        exit 1
    fi
fi

step_footer

# ==============================================================================
# Step 2: Python Virtual Environment (.venv)
# ==============================================================================
step_header "2" "$TOTAL_STEPS" "Python Virtual Environment Setup"

VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    run_spinner "Creating isolated Python virtualenv (.venv)" python3 -m venv "$VENV_DIR"
else
    tui_info "Existing virtual environment found in .venv"
fi

# Activate .venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

VENV_PY_VER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
tui_success "Virtualenv activated: Python ${VENV_PY_VER} (${VENV_DIR})"

step_footer

# ==============================================================================
# Step 3: Install Python Dependencies
# ==============================================================================
step_header "3" "$TOTAL_STEPS" "Python Dependencies Installation"

# Ensure requirements.txt exists
if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    cat > "$PROJECT_DIR/requirements.txt" << 'EOF'
# Regolo + SoL-Pi Tutorial Dependencies
python-dotenv>=1.0.0
rich>=13.7.0
requests>=2.31.0
EOF
    tui_info "Created requirements.txt with essential packages"
fi

run_spinner "Upgrading pip to latest version" pip install --upgrade pip
run_spinner "Installing requirements (python-dotenv, rich, requests)" pip install -r "$PROJECT_DIR/requirements.txt"

tui_success "All Python dependencies installed successfully in .venv"

step_footer

# ==============================================================================
# Step 4: Regolo Provider in Pi (models.json)
# ==============================================================================
step_header "4" "$TOTAL_STEPS" "Pi Provider Registration (Regolo AI)"

# Register Regolo provider and qwen3.5-122b model into ~/.pi/agent/models.json
run_spinner "Configuring Regolo AI provider in ~/.pi/agent/models.json" python3 -c '
import json, os
from pathlib import Path

p = Path.home() / ".pi" / "agent" / "models.json"
p.parent.mkdir(parents=True, exist_ok=True)
data = json.loads(p.read_text()) if p.exists() else {"providers": {}}
providers = data.setdefault("providers", {})
regolo = providers.setdefault("regolo", {
    "baseUrl": "https://api.regolo.ai/v1",
    "api": "openai-completions",
    "apiKey": "$REGOLO_API_KEY",
    "models": []
})
models = regolo.setdefault("models", [])
ids = {m.get("id") for m in models if isinstance(m, dict)}
if "qwen3.5-122b" not in ids:
    models.insert(0, {
        "id": "qwen3.5-122b",
        "name": "Regolo Qwen 3.5 122B",
        "input": ["text"],
        "contextWindow": 262144,
        "maxTokens": 16384,
        "cost": { "input": 1.0, "output": 4.2, "cacheRead": 0, "cacheWrite": 0 }
    })
p.write_text(json.dumps(data, indent=2) + "\n")
'

tui_success "Regolo provider registered (Base URL: https://api.regolo.ai/v1)"
tui_success "Model 'qwen3.5-122b' configured (262k context window)"

step_footer

# ==============================================================================
# Step 5: Download / Clone SoL-Pi into this folder
# ==============================================================================
step_header "5" "$TOTAL_STEPS" "SoL-Pi Repository Download"

SOLE_PI_DIR="$PROJECT_DIR/SoL-Pi"

if [ -d "$SOLE_PI_DIR/.git" ]; then
    tui_info "Found existing SoL-Pi checkout in ./SoL-Pi"
    COMMIT_HASH=$(git -C "$SOLE_PI_DIR" rev-parse --short HEAD 2>/dev/null || echo "main")
    tui_success "Using local SoL-Pi at commit: ${COMMIT_HASH}"
else
    rm -rf "$SOLE_PI_DIR"
    run_spinner "Cloning SoL-Pi from github.com/NVlabs/SoL-Pi into ./SoL-Pi" git clone --depth 1 https://github.com/NVlabs/SoL-Pi.git "$SOLE_PI_DIR"
    COMMIT_HASH=$(git -C "$SOLE_PI_DIR" rev-parse --short HEAD 2>/dev/null || echo "main")
    tui_success "Cloned SoL-Pi into ./SoL-Pi (commit: ${COMMIT_HASH})"
fi

step_footer

# ==============================================================================
# Step 6: Install SoL-Pi as Local Pi Package
# ==============================================================================
step_header "6" "$TOTAL_STEPS" "Pi Local Package Registration"

# Ensure .pi directory exists
mkdir -p "$PROJECT_DIR/.pi"

run_spinner "Registering ./SoL-Pi into local Pi project (.pi/settings.json)" pi install "$SOLE_PI_DIR" --local --approve

tui_success "SoL-Pi package linked locally to this project"
tui_info "Verified with Pi package manager:"
pi list --approve | while IFS= read -r line; do
    echo -e "  ${G_ACCENT}│${C_RESET}     ${C_GRAY}${line}${C_RESET}"
done

step_footer

# ==============================================================================
# Step 7: Create Benchmark Profile (.pi/sol-pi.json)
# ==============================================================================
step_header "7" "$TOTAL_STEPS" "SoL-Pi Benchmark Profile Setup"

cat > "$PROJECT_DIR/.pi/sol-pi.json" << 'EOF'
{
  "version": 1,
  "actionFusion": true,
  "observationPack": true,
  "evidencePreservingReducer": false,
  "onlineContextCompact": false,
  "cacheWriteReadRatio": 12.5
}
EOF

tui_success "Generated .pi/sol-pi.json (Arm B profile)"
echo -e "  ${G_ACCENT}│${C_RESET}     ${C_GRAY}• Action Fusion               :${C_RESET} ${G_BOLD}ON${C_RESET}"
echo -e "  ${G_ACCENT}│${C_RESET}     ${C_GRAY}• ObservationPack             :${C_RESET} ${G_BOLD}ON${C_RESET}"
echo -e "  ${G_ACCENT}│${C_RESET}     ${C_GRAY}• EvidencePreservingReducer   :${C_RESET} ${C_GRAY}OFF (local profile)${C_RESET}"
echo -e "  ${G_ACCENT}│${C_RESET}     ${C_GRAY}• OnlineContextCompact (OCC)  :${C_RESET} ${C_GRAY}OFF (local profile)${C_RESET}"

step_footer

# ==============================================================================
# Step 8: Credentials & Verification (.env)
# ==============================================================================
step_header "8" "$TOTAL_STEPS" "Regolo Credentials & Validation"

ENV_FILE="$PROJECT_DIR/.env"
ENV_EXAMPLE="$PROJECT_DIR/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        tui_info "Created .env from .env.example"
    else
        echo "REGOLO_API_KEY=your-regolo-api-key-here" > "$ENV_FILE"
        tui_info "Created default .env template"
    fi
else
    tui_info "Existing .env file detected"
fi

# Read REGOLO_API_KEY from .env or environment
CURRENT_KEY="${REGOLO_API_KEY:-}"
if [ -z "$CURRENT_KEY" ] || [ "$CURRENT_KEY" = "your-regolo-api-key-here" ]; then
    if [ -f "$ENV_FILE" ]; then
        EXTRACTED_KEY=$(grep -E '^REGOLO_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" | tr -d ' ' || true)
        if [ -n "$EXTRACTED_KEY" ] && [ "$EXTRACTED_KEY" != "your-regolo-api-key-here" ]; then
            CURRENT_KEY="$EXTRACTED_KEY"
        fi
    fi
fi

# If interactive and key is empty or default placeholder, offer to paste it
if [ -t 0 ] && { [ -z "$CURRENT_KEY" ] || [ "$CURRENT_KEY" = "your-regolo-api-key-here" ]; }; then
    echo -e "  ${G_ACCENT}│${C_RESET}"
    echo -e "  ${G_ACCENT}│${C_RESET}  ${C_YELLOW}No valid REGOLO_API_KEY found in .env.${C_RESET}"
    echo -e "  ${G_ACCENT}│${C_RESET}  ${C_GRAY}Get a 30-day free trial key at:${C_RESET} ${C_CYAN}https://regolo.ai/pricing${C_RESET}"
    echo -ne "  ${G_ACCENT}│${C_RESET}  ${G_BOLD}Paste your REGOLO_API_KEY${C_RESET} ${C_GRAY}(or press Enter to skip):${C_RESET} "
    read -r USER_INPUT_KEY
    if [ -n "$USER_INPUT_KEY" ]; then
        CURRENT_KEY="$USER_INPUT_KEY"
        # Update .env
        if grep -q '^REGOLO_API_KEY=' "$ENV_FILE"; then
            python3 -c "
import sys
p = '$ENV_FILE'
lines = open(p).readlines()
with open(p, 'w') as f:
    for l in lines:
        if l.startswith('REGOLO_API_KEY='):
            f.write(f'REGOLO_API_KEY=$CURRENT_KEY\n')
        else:
            f.write(l)
"
        else
            echo "REGOLO_API_KEY=$CURRENT_KEY" >> "$ENV_FILE"
        fi
        tui_success "Updated REGOLO_API_KEY in .env"
    fi
fi

export REGOLO_API_KEY="${CURRENT_KEY:-}"

if [ -n "$REGOLO_API_KEY" ] && [ "$REGOLO_API_KEY" != "your-regolo-api-key-here" ]; then
    tui_success "REGOLO_API_KEY is configured"
    # Test model listing
    MODEL_CHECK=$(pi --list-models regolo 2>/dev/null || true)
    if echo "$MODEL_CHECK" | grep -q "qwen3.5-122b"; then
        tui_success "Pi validated connectivity with Regolo provider!"
    else
        tui_warn "Pi provider configured, but listing models returned no matches or connection pending"
    fi
else
    tui_warn "REGOLO_API_KEY is currently empty or set to placeholder."
    tui_info "Edit .env and add your key from https://regolo.ai/pricing before running paid benchmarks."
fi

step_footer

# ==============================================================================
# GRAND FINALE: SUMMARY & LAUNCH GUIDE
# ==============================================================================
echo -e "  ${G_BOLD}╔══════════════════════════════════════════════════════════════════════════╗${C_RESET}"
echo -e "  ${G_BOLD}║${C_RESET}                      ${G_BOLD}✔ SETUP COMPLETED SUCCESSFULLY!${C_RESET}                     ${G_BOLD}║${C_RESET}"
echo -e "  ${G_BOLD}╚══════════════════════════════════════════════════════════════════════════╝${C_RESET}\n"

echo -e "  ${G_ACCENT}All components are ready for the benchmark:${C_RESET}"
echo -e "  ${G_BOLD}[ ✔ ]${C_RESET} Python Virtual Environment : ${C_WHITE}.venv (activated)${C_RESET}"
echo -e "  ${G_BOLD}[ ✔ ]${C_RESET} Python Modules Installed   : ${C_WHITE}python-dotenv, rich, requests${C_RESET}"
echo -e "  ${G_BOLD}[ ✔ ]${C_RESET} SoL-Pi Source Cloned       : ${C_WHITE}./SoL-Pi (local)${C_RESET}"
echo -e "  ${G_BOLD}[ ✔ ]${C_RESET} Pi Local Extension Linked  : ${C_WHITE}.pi/settings.json${C_RESET}"
echo -e "  ${G_BOLD}[ ✔ ]${C_RESET} Benchmark Profile Active   : ${C_WHITE}.pi/sol-pi.json (Arm B)${C_RESET}"
echo -e "  ${G_BOLD}[ ✔ ]${C_RESET} Regolo Provider in Pi      : ${C_WHITE}qwen3.5-122b @ api.regolo.ai/v1${C_RESET}\n"

echo -e "  ${G_ACCENT}──────────────────────────────────────────────────────────────────────────${C_RESET}"
echo -e "  ${G_BOLD}🚀 HOW TO RUN THE BENCHMARK:${C_RESET}"
echo -e "  ${G_ACCENT}──────────────────────────────────────────────────────────────────────────${C_RESET}\n"

echo -e "  ${C_GRAY}1. Using the convenient launcher script:${C_RESET}"
echo -e "     ${G_BOLD}./run.sh --max-tasks 1${C_RESET}             ${C_GRAY}# Quick 1-task pilot smoke test${C_RESET}"
echo -e "     ${G_BOLD}./run.sh${C_RESET}                           ${C_GRAY}# Full 51-task two-arm benchmark${C_RESET}"
echo -e "     ${G_BOLD}./run.sh --dry-run${C_RESET}                 ${C_GRAY}# Generate test fixtures (no API spend)${C_RESET}\n"

echo -e "  ${C_GRAY}2. Or run directly with Python in .venv:${C_RESET}"
echo -e "     ${G_ACCENT}source .venv/bin/activate${C_RESET}"
echo -e "     ${G_ACCENT}python3 sol_pi_two_arms.py --project . --max-tasks 1${C_RESET}\n"

echo -e "  ${C_GRAY}Need a free trial API key? Claim 30 days free at:${C_RESET}"
echo -e "  ${C_CYAN}👉 https://regolo.ai/pricing${C_RESET}\n"
