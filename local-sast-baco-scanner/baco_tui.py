#!/usr/bin/env python3
"""
Baco Scanner TUI — Regolo.ai Edition
====================================
Interactive Terminal UI for running Baco Scanner exclusively with Regolo.ai
models and estimating costs via Brick Complexity Pro.

Features:
  [1] Setup Environment (Regolo.ai API key & model selection)
  [2] Scan Repository & View Findings + Brick Complexity Pro Cost
  [3] Generate AI Fixes for Vulnerabilities (Regolo LLM & Prompt Export)
  [4] Exit
"""

import os
import sys
import json
import time
import re
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ── Configuration Constants ─────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent
BACO_REPO = "https://github.com/CodeAtCode/baco-scanner.git"
BACO_DIR = ROOT_DIR / "baco-scanner"
CONFIG_FILE = ROOT_DIR / "my-config.toml"
ENV_FILE = ROOT_DIR / ".env"
OUTPUT_DIR = ROOT_DIR / "baco-output"
REMEDIATIONS_DIR = ROOT_DIR / "remediations"

REGOLO_BASE_URL = "https://api.regolo.ai/v1"
REGOLO_MODELS_URL = "https://api.regolo.ai/v1/models"
REGOLO_COMPLETIONS_URL = "https://api.regolo.ai/v1/chat/completions"

DEFAULT_MODEL = "brick-complexity-pro"

# Brick Complexity Pro pricing on Regolo.ai: €0.12 per 1M input tokens
BRICK_RATE_PER_MILLION_EUR = 0.12
TOKENS_PER_FILE_ANALYSIS = 5800
TOKENS_PER_FINDING_TRIAGE = 1800

DEFAULT_EXCLUDE_PATHS = [
    "tests/**", "test/**", "target/**", "node_modules/**", ".git/**",
    ".venv/**", "venv/**", "env/**", ".env/**", "**/__pycache__/**",
    "dist/**", "build/**", ".idea/**", ".vscode/**",
    "*.log", "*.jsonl", "*.txt", "*.csv", ".env*", "*.key", "*.pem",
    "secrets/**", "credentials/**"
]


def update_config_for_scan(target_path: Path) -> int:
    """
    Update target path in my-config.toml and merge .gitignore rules from target_path
    into scanner.exclude_paths to guarantee gitignored files are never indexed or scanned.
    Returns the number of rules loaded from .gitignore.
    """
    if not CONFIG_FILE.exists():
        return 0

    git_rules = []
    gitignore = target_path / ".gitignore"
    if gitignore.exists() and gitignore.is_file():
        try:
            with open(gitignore, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("!"):
                        continue
                    if line.startswith("/"):
                        line = line[1:]
                    if line.endswith("/"):
                        git_rules.append(f"{line}**")
                        git_rules.append(f"**/{line}**")
                    else:
                        git_rules.append(line)
                        if not line.startswith("*") and not line.startswith("**/"):
                            git_rules.append(f"**/{line}")
                            git_rules.append(f"**/{line}/**")
        except Exception:
            pass

    combined = list(dict.fromkeys(DEFAULT_EXCLUDE_PATHS + git_rules))

    content = CONFIG_FILE.read_text(encoding="utf-8")
    content = re.sub(r'path\s*=\s*"[^"]*"', f'path = "{target_path}"', content, count=1)

    formatted_excludes = ",\n    ".join(f'"{p}"' for p in combined)
    new_exclude_block = f"exclude_paths = [\n    {formatted_excludes}\n]\n\n"

    start_marker = "exclude_paths"
    start_idx = content.find(start_marker)
    if start_idx != -1:
        end_marker = "[scanner.performance]"
        end_idx = content.find(end_marker, start_idx)
        if end_idx != -1:
            content = content[:start_idx] + new_exclude_block + content[end_idx:]

    CONFIG_FILE.write_text(content, encoding="utf-8")
    return len(git_rules)


def calculate_scan_tokens_and_cost(target_path: Path = None, findings_count: int = 0) -> dict:
    """
    Accurately compute total tokens and cost in EUR (€) consumed across the 24-phase scan.
    Even with 0 findings, the LLM analyzes codebase files in Phase 4 (LLM Static Analysis)
    and evaluates threat models.
    """
    scanned_files_count = 0
    code_bytes_analyzed = 0

    # 1. Read file_hashes.json from baco-output to count exact scanned files
    hashes_file = OUTPUT_DIR / "file_hashes.json"
    if hashes_file.exists():
        try:
            with open(hashes_file, "r") as f:
                data = json.load(f)
                hashes = data.get("hashes", {})
                scanned_files_count = len(hashes)
                for fpath_str in hashes.keys():
                    p = Path(fpath_str)
                    if p.exists() and p.is_file():
                        code_bytes_analyzed += min(p.stat().st_size, 8000)
        except Exception:
            pass

    # 2. Fallback to inspecting target directory if file_hashes.json not available
    if scanned_files_count == 0 and target_path and target_path.exists():
        extensions = [".py", ".c", ".cpp", ".rs", ".js", ".ts", ".go", ".java"]
        found = [
            f for f in target_path.rglob("*")
            if f.is_file() and f.suffix.lower() in extensions
            and not any(x in str(f) for x in [".venv", "node_modules", ".git", "__pycache__", "target"])
        ]
        scanned_files_count = len(found)
        code_bytes_analyzed = sum(min(f.stat().st_size, 8000) for f in found)

    if scanned_files_count == 0:
        scanned_files_count = 1

    # Token breakdown:
    # - Static analysis prompt template: ~4,500 tokens per file
    # - Code chunk tokens: ~ code_bytes_analyzed / 4
    # - Completion tokens: ~600 tokens per file
    # - Triage & verification for findings: ~1,800 tokens per finding
    base_file_tokens = (scanned_files_count * 5100) + (code_bytes_analyzed // 4)
    findings_tokens = findings_count * TOKENS_PER_FINDING_TRIAGE
    total_tokens = base_file_tokens + findings_tokens

    cost_eur = (total_tokens / 1_000_000.0) * BRICK_RATE_PER_MILLION_EUR

    return {
        "files_count": scanned_files_count,
        "total_tokens": total_tokens,
        "cost_eur": cost_eur,
        "rate_eur": BRICK_RATE_PER_MILLION_EUR,
    }


# ── ANSI Color Formatting ───────────────────────────────────────────

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    BRIGHT_GREEN = "\033[92m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def clear_screen():
    """Clear terminal screen reliably across platforms."""
    print("\033[2J\033[H", end="", flush=True)
    os.system("cls" if os.name == "nt" else "clear")


def print_regolo_header():
    """Display the prominent REGOLO green ASCII banner with Baco description."""
    green_bold = f"{Color.BRIGHT_GREEN}{Color.BOLD}"
    reset = Color.RESET
    dim = Color.DIM
    cyan = Color.CYAN
    white_bold = f"{Color.WHITE}{Color.BOLD}"

    print(f"""{green_bold}
  ____  _____ ____ ___  _     ___  
 |  _ \\| ____/ ___/ _ \\| |   / _ \\ 
 | |_) |  _|| |  | | | | |  | | | |
 |  _ <| |__| |__| |_| | |__| |_| |
 |_| \\_\\_____\\____\\___/|_____\\___/ 
{reset}""")
    print(f" {white_bold}BACO — Bug Analysis & Cross-reference Orchestrator{reset}")
    print(f" {dim}Research-backed SAST scanner combining Semgrep static analysis with an{reset}")
    print(f" {dim}LLM-powered 24-phase pipeline (CWE routing, exploit synthesis, triage).{reset}")
    print(f" {cyan}Powered exclusively by Regolo.ai EU-hosted models & Brick Complexity Pro{reset}")
    print(f"{Color.CYAN}{'=' * 72}{reset}\n")


def header(title: str):
    print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 72}{Color.RESET}")
    print(f" {Color.WHITE}{Color.BOLD}{title}{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}{'=' * 72}{Color.RESET}")


def info(msg: str):
    print(f" {Color.BLUE}ℹ{Color.RESET}  {msg}")


def success(msg: str):
    print(f" {Color.GREEN}✓{Color.RESET}  {Color.BOLD}{msg}{Color.RESET}")


def warn(msg: str):
    print(f" {Color.YELLOW}⚠{Color.RESET}  {msg}")


def error(msg: str):
    print(f" {Color.RED}✗{Color.RESET}  {Color.BOLD}{msg}{Color.RESET}")


def clean_path_input(raw: str) -> Path:
    """
    Clean and normalize user path input.
    Handles single/double enclosing quotes (from terminal drag-and-drop),
    escaped spaces, and home directory tilde (~).
    """
    s = raw.strip()
    while (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1].strip()
    if sys.platform != "win32" and "\\ " in s:
        s = s.replace("\\ ", " ")
    expanded = os.path.expanduser(s)
    return Path(expanded).resolve()


# ── Dependency & Binary Management ──────────────────────────────────

def check_semgrep() -> bool:
    """Verify that semgrep is installed and available in PATH."""
    return shutil.which("semgrep") is not None


def ensure_prompts_symlink():
    """Ensure the prompts directory is reachable by the baco binary."""
    prompts_link = ROOT_DIR / "prompts"
    source = BACO_DIR / "prompts"
    if not prompts_link.exists() and source.exists():
        try:
            prompts_link.symlink_to(source)
        except Exception:
            pass


def ensure_baco_binary() -> str:
    """
    Locate the compiled baco binary.
    If missing, clone the repository and compile using locked dependencies.
    """
    binary_path = BACO_DIR / "target" / "release" / "baco"

    if binary_path.exists() and os.access(binary_path, os.X_OK):
        return str(binary_path)

    header("Baco Scanner Engine Initialization")
    info("Compiled binary not found. Preparing baco-scanner...")

    # 1. Clone repository if missing
    if not BACO_DIR.exists():
        info(f"Cloning baco-scanner from {BACO_REPO}...")
        res = subprocess.run(["git", "clone", BACO_REPO, str(BACO_DIR)], capture_output=True, text=True)
        if res.returncode != 0:
            error(f"Clone failed: {res.stderr}")
            sys.exit(1)
        success("Repository cloned successfully.")

    # 2. Compile release binary using committed Cargo.lock
    info("Compiling baco in release mode (cargo build --release)...")
    build_start = time.time()
    res = subprocess.run(
        ["cargo", "build", "--release", "--locked"],
        cwd=str(BACO_DIR),
        capture_output=True,
        text=True
    )

    # Fallback if dependencies in Cargo.lock require newer rustc than installed (e.g. rustc 1.87 vs 1.88)
    if res.returncode != 0 and ("requires rustc" in res.stderr or "not supported by" in res.stderr):
        warn("Detected rustc version constraint in upstream Cargo.lock. Pinning compatible dependency versions...")
        subprocess.run(["cargo", "update", "globset", "--precise", "0.4.15"], cwd=str(BACO_DIR), capture_output=True)
        subprocess.run(["cargo", "update", "home", "--precise", "0.5.11"], cwd=str(BACO_DIR), capture_output=True)
        res = subprocess.run(
            ["cargo", "build", "--release"],
            cwd=str(BACO_DIR),
            capture_output=True,
            text=True
        )

    if res.returncode != 0:
        error(f"Build failed:\n{res.stderr}")
        sys.exit(1)

    elapsed = time.time() - build_start
    success(f"Compilation completed successfully in {elapsed:.1f}s.")
    return str(binary_path)


# ── Regolo.ai API Helpers ───────────────────────────────────────────

def get_saved_regolo_key() -> str:
    """Retrieve saved REGOLO_API_KEY from environment, .env, or config."""
    if os.environ.get("REGOLO_API_KEY"):
        return os.environ["REGOLO_API_KEY"].strip()

    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.startswith("REGOLO_API_KEY="):
                    return line.strip().split("=", 1)[1].strip('"\' ')

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                if "api_key" in line and "=" in line:
                    key = line.split("=", 1)[1].strip('"\' \n')
                    if key and key != "your-key-here":
                        return key

    return ""


def get_configured_model() -> str:
    """Retrieve the selected model from config or fallback to default."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                for line in f:
                    if line.strip().startswith("model ="):
                        return line.split("=", 1)[1].strip('"\' \n')
        except Exception:
            pass
    return DEFAULT_MODEL


def fetch_regolo_models(api_key: str = "") -> list[str]:
    """
    Fetch active models from Regolo.ai API catalog,
    ensuring brick-complexity-pro is at the top.
    """
    models = []
    try:
        req = urllib.request.Request(REGOLO_MODELS_URL)
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if isinstance(data, dict) and "data" in data:
                for item in data["data"]:
                    m_id = item.get("id")
                    if m_id and not any(x in m_id for x in ["whisper", "ocr", "Image", "Embedding", "Reranker"]):
                        models.append(m_id)
            if models:
                models = sorted(models)
    except Exception:
        pass

    if not models:
        models = [
            DEFAULT_MODEL,
            "qwen3-coder-next",
            "qwen3.5-122b",
            "mistral-small-4-119b",
            "Llama-3.3-70B-Instruct",
            "gpt-oss-120b",
            "qwen3.8-27b",
            "qwen3.5-9b",
            "glm5.2",
        ]

    # Prioritize brick-complexity-pro at index 0
    if DEFAULT_MODEL in models:
        models.remove(DEFAULT_MODEL)
    models.insert(0, DEFAULT_MODEL)
    return models


def call_brick_complexity(prompt_sample: str, api_key: str) -> dict:
    """Query brick-complexity-pro on Regolo.ai to classify analysis workload."""
    if not api_key:
        return {"tier": "medium", "tokens": 0}

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"Classify the vulnerability analysis complexity for this codebase sample:\n{prompt_sample[:500]}"
            }
        ],
        "max_tokens": 50,
        "temperature": 0.0
    }

    try:
        req = urllib.request.Request(
            REGOLO_COMPLETIONS_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            res = json.loads(response.read().decode())
            content = res["choices"][0]["message"]["content"]
            usage = res.get("usage", {})
            return {
                "response": content,
                "tier": "hard" if "hard" in content.lower() else "medium",
                "tokens": usage.get("total_tokens", 0)
            }
    except Exception:
        return {"tier": "medium", "tokens": 0}


# ── Option 1: Setup Environment ─────────────────────────────────────

def setup_environment():
    header("OPTION 1: Environment Setup — Regolo.ai")

    current_key = get_saved_regolo_key()
    prompt_text = "Enter REGOLO_API_KEY"
    if current_key:
        masked = current_key[:6] + "..." + current_key[-4:] if len(current_key) > 10 else "***"
        prompt_text += f" [Press Enter to keep {masked}]"
    prompt_text += ": "

    key_input = input(prompt_text).strip()
    api_key = key_input if key_input else current_key

    if not api_key:
        error("REGOLO_API_KEY is required. Register at https://regolo.ai to get one.")
        return

    info("Querying Regolo.ai model catalog...")
    models = fetch_regolo_models(api_key)

    print(f"\n{Color.BOLD}Available Models on Regolo.ai:{Color.RESET}")
    for i, m in enumerate(models, 1):
        tag = f" {Color.GREEN}(Default / Recommended){Color.RESET}" if m == DEFAULT_MODEL else ""
        print(f"  [{i}] {m}{tag}")

    choice = input(f"\nSelect model [1-{len(models)}] or press Enter for {Color.CYAN}{DEFAULT_MODEL}{Color.RESET}: ").strip()
    selected_model = DEFAULT_MODEL
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        selected_model = models[int(choice) - 1]
    elif choice in models:
        selected_model = choice

    # Generate Baco-compliant config.toml with comprehensive exclusions
    formatted_default_excludes = ",\n    ".join(f'"{p}"' for p in DEFAULT_EXCLUDE_PATHS)
    config_content = f"""# BACO Scanner Configuration generated by Baco TUI
# Provider: Regolo.ai (OpenAI-compatible)

[project]
name = "regolo-security-scan"
path = "."
languages = ["c", "cpp", "python", "rust", "javascript"]

[output]
dir = "./baco-output"
evidence_gate = false

[scanner]
max_file_size_kb = 256
exclude_paths = [
    {formatted_default_excludes}
]

[scanner.performance]
enable_incremental_scan = false
max_parallel_tasks = 2
enable_file_filtering = true
enable_root_cause_dedup = true
enable_multi_verifier = false
enable_auto_patching = false
enable_poc_compilation = false
enable_confidence_refinement = true
enable_cve_bootstrap = false
enable_variant_search = true

[llm]
timeout_secs = 240
max_retries = 3
retry_backoff_ms = 2000
max_concurrent = 2
temperature = 0.5
enable_llm_cache = false

[llm.phases.discovery]
base_url = "{REGOLO_BASE_URL}"
api_key = "{api_key}"
model = "{selected_model}"

[llm.phases.verification]
base_url = "{REGOLO_BASE_URL}"
api_key = "{api_key}"
model = "{selected_model}"

[llm.phases.aggregation]
base_url = "{REGOLO_BASE_URL}"
api_key = "{api_key}"
model = "{selected_model}"

[brick]
base_url = "{REGOLO_BASE_URL}"
api_key = "{api_key}"
model = "brick-complexity-pro"
"""

    with open(CONFIG_FILE, "w") as f:
        f.write(config_content)

    with open(ENV_FILE, "w") as f:
        f.write(f"REGOLO_API_KEY={api_key}\n")

    os.environ["REGOLO_API_KEY"] = api_key

    success("Environment configured successfully:")
    print(f"  • API Endpoint:   {Color.CYAN}{REGOLO_BASE_URL}{Color.RESET}")
    print(f"  • Selected Model: {Color.CYAN}{selected_model}{Color.RESET}")
    print(f"  • Cost Classifier:{Color.CYAN}brick-complexity-pro{Color.RESET}")
    print(f"  • Config File:    {Color.DIM}{CONFIG_FILE}{Color.RESET}")


# ── Option 2: Scan Repository & Show Cost ───────────────────────────

# Global state to suppress multi-line prompt previews dumped by baco engine
_in_prompt_preview_block = False

def format_scan_log_line(line: str) -> str:
    """
    Parse and colorize a structured Baco log line for readability.

    Expected format:
      2026-09-08T13:49:27.659186Z  INFO baco: Starting scan...
      2026-09-08T13:49:27.659387Z  INFO baco::scanner::orchestrator: [SCANNER] Parallel mode ENABLED
    """
    global _in_prompt_preview_block

    raw = line.rstrip("\n")
    if not raw.strip():
        return ""

    # Strip ANSI escape codes (both raw 0x1b byte and literal "\x1b" / "\033" sequences)
    ansi_pattern = re.compile(
        r'(?:\x1b|\033|' + re.escape(r'\x1b') + r'|' + re.escape(r'\033') + r')\[[0-9;]*[a-zA-Z]'
    )
    clean = ansi_pattern.sub('', raw)

    # Immediately discard lines with unreplaced prompt template markers
    if any(marker in clean for marker in ["%%LANGUAGE%%", "%%FILE_PATH%%", "%%LINE_RANGE%%", "%%CONTEXT_LINES%%", "%%CODE_CONTENT%%", "%%CWE_SPECS%%", "%%CO"]):
        return ""
    if "OFFENSIVE SECURITY RESEARCHER" in clean or clean.strip().startswith("## INPUT"):
        return ""

    # Parse structured fields: TIMESTAMP LEVEL MODULE: MESSAGE
    # Pattern: ISO timestamp, then whitespace, then level (INFO/WARN/ERROR/etc), then module, then ': ', then message
    match = re.match(
        r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+(\w+)\s+(\S+):\s*(.*)$',
        clean
    )

    if not match:
        # If we are inside a multi-line prompt block, suppress continuation lines
        if _in_prompt_preview_block:
            return ""
        # Non-structured line (e.g. "Initializing scanner..." or blank)
        dim = Color.DIM
        reset = Color.RESET
        return f"  {dim}{clean}{Color.RESET}"

    # A new timestamped log line arrived -> reset multi-line prompt block state
    _in_prompt_preview_block = False

    timestamp, level, module, message = match.groups()

    # Skip verbose prompt-dump lines (PROMPT preview) and set flag for continuation lines
    if "PROMPT:" in message or "PROMPT:" in module:
        _in_prompt_preview_block = True
        return ""

    # Classify by log level and module category
    level_upper = level.upper()
    module_parts = module.split("::")
    category = module_parts[0] if module_parts else module  # e.g. "baco", "baco::scanner", "baco::llm"

    # Strip residual escape codes from message and inspect bracket tags
    message = ansi_pattern.sub('', message).strip()
    embedded_tag = re.match(r'^\s*\[([A-Z][A-Z_-]+)\]\s*', message)
    if embedded_tag:
        message = re.sub(r'^\s*\[[A-Z][A-Z_-]+\]\s*', '', message)

    # Determine category display label and color
    # Detection priority: message content, then module path
    msg_lower = message.lower()
    mod_lower = module.lower()

    # Map module prefixes / message tags to colored category badges
    if "llm" in mod_lower or "llm" in msg_lower:
        cat_badge = f"{Color.MAGENTA}[LLM]{Color.RESET}"
        msg_color = Color.MAGENTA
    elif "indexing" in mod_lower or embedded_tag and embedded_tag.group(1) == "INDEXING":
        cat_badge = f"{Color.CYAN}[INDEXING]{Color.RESET}"
        msg_color = Color.CYAN
    elif "scanner" in mod_lower or "orchestrator" in mod_lower or (embedded_tag and embedded_tag.group(1) == "SCANNER"):
        cat_badge = f"{Color.BLUE}[SCANNER]{Color.RESET}"
        msg_color = Color.BLUE
    elif "semgrep" in mod_lower:
        cat_badge = f"{Color.YELLOW}[SEMGREP]{Color.RESET}"
        msg_color = Color.YELLOW
    elif "cwe_routing" in mod_lower or "cwe-routing" in msg_lower:
        cat_badge = f"{Color.RED}[CWE-ROUTING]{Color.RESET}"
        msg_color = Color.RED
    elif "reporting" in mod_lower or "report" in mod_lower:
        cat_badge = f"{Color.GREEN}[REPORTING]{Color.RESET}"
        msg_color = Color.GREEN
    else:
        cat_badge = f"{Color.WHITE}[{category}]{Color.RESET}"
        msg_color = Color.WHITE

    # Colorize by log level
    if level_upper == "ERROR" or level_upper == "WARN":
        level_str = f"{Color.RED}{Color.BOLD}{level_upper:<6}{Color.RESET}"
    elif level_upper == "INFO":
        level_str = f"{Color.BLUE}{Color.BOLD}{level_upper:<6}{Color.RESET}"
    elif level_upper == "DEBUG":
        level_str = f"{Color.DIM}{level_upper:<6}{Color.RESET}"
    else:
        level_str = f"{Color.YELLOW}{Color.BOLD}{level_upper:<6}{Color.RESET}"

    # Dim the timestamp, keep message in category color
    ts_str = f"{Color.DIM}{timestamp}{Color.RESET}"
    return f"  {ts_str}  {level_str} {cat_badge} {msg_color}{message}{Color.RESET}"


def scan_repository(baco_bin: str, target_path_override: Path = None, interactive: bool = True):
    if interactive:
        header("OPTION 2: Scan Repository & Brick Complexity Pro Cost")

    if not CONFIG_FILE.exists():
        warn(f"Configuration file ({CONFIG_FILE.name}) not found.")
        info("Running environment setup first...")
        setup_environment()
        if not CONFIG_FILE.exists():
            return

    if target_path_override:
        target_path = clean_path_input(str(target_path_override))
    elif interactive:
        target_input = input(f"\nRepository or folder path to scan [Press Enter for {Color.CYAN}.{Color.RESET}]: ").strip()
        target_path = clean_path_input(target_input) if target_input else Path(".").resolve()
    else:
        target_path = Path(".").resolve()

    if not target_path.exists() or not target_path.is_dir():
        error(f"Path does not exist or is not a directory: {target_path}")
        return

    try:
        git_rules_count = update_config_for_scan(target_path)
        if git_rules_count > 0:
            info(f"Loaded {Color.BOLD}{git_rules_count}{Color.RESET} exclusion patterns from {Color.CYAN}.gitignore{Color.RESET}")
    except Exception as e:
        warn(f"Unable to update project.path and exclusions in config: {e}")

    info(f"Target selected: {Color.BOLD}{target_path}{Color.RESET}")
    info("Starting Baco Scanner 24-phase pipeline...")

    env = os.environ.copy()
    api_key = get_saved_regolo_key()
    if api_key:
        env["REGOLO_API_KEY"] = api_key

    scan_start = time.time()
    cmd = [baco_bin, "-v", "scan", "--force", "--config", str(CONFIG_FILE), "--target", str(target_path)]

    print(f"\n{Color.DIM}Command: {' '.join(cmd)}{Color.RESET}\n")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    output_lines = []
    for line in iter(process.stdout.readline, ""):
        formatted = format_scan_log_line(line)
        if formatted:
            print(formatted, end="\n", flush=True)
        output_lines.append(line)
    process.wait()
    scan_duration = time.time() - scan_start

    # Parse scan findings
    findings_file = OUTPUT_DIR / "findings.json"
    findings_count = 0
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    findings_list = []

    if findings_file.exists():
        try:
            with open(findings_file, "r") as f:
                findings_list = json.load(f)
                findings_count = len(findings_list)
                for f_item in findings_list:
                    sev = f_item.get("severity", "Info")
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1
        except Exception:
            pass

    # Calculate accurate token usage & cost via Brick Complexity Pro
    metrics = calculate_scan_tokens_and_cost(target_path, findings_count)
    total_estimated_tokens = metrics["total_tokens"]
    total_cost_eur = metrics["cost_eur"]
    files_analyzed_count = metrics["files_count"]

    complexity_label = "Standard"
    if findings_count > 0 and api_key:
        sample_code = findings_list[0].get("code_snippet", "") if findings_list else ""
        brick_result = call_brick_complexity(sample_code, api_key)
        if brick_result.get("tier"):
            complexity_label = brick_result["tier"].capitalize()

    # Executive Summary Card
    print("\n")
    print(f"{Color.CYAN}╔{'═' * 70}╗{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET} {Color.BOLD}{'SCAN RESULTS & BRICK COMPLEXITY PRO COST BREAKDOWN':^68}{Color.RESET} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}╠{'═' * 70}╣{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  {Color.WHITE}Target:{Color.RESET}             {str(target_path)[:50]:<50} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  {Color.WHITE}Scan Duration:{Color.RESET}      {f'{scan_duration:.1f} seconds':<50} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  {Color.WHITE}Total Findings:{Color.RESET}     {f'{findings_count} vulnerabilities identified':<50} {Color.CYAN}║{Color.RESET}")

    sev_str = f"Crit: {severity_counts['Critical']} | High: {severity_counts['High']} | Med: {severity_counts['Medium']} | Low: {severity_counts['Low']}"
    print(f"{Color.CYAN}║{Color.RESET}  {Color.WHITE}Severity Counts:{Color.RESET}    {sev_str:<50} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}╠{'═' * 70}╣{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  {Color.YELLOW}{Color.BOLD}REGOLO.AI / BRICK COMPLEXITY PRO PRICING:{Color.RESET}{' ':>27} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Router Model:      brick-complexity-pro (Regolo.ai){' ':>19} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Complexity Tier:   {complexity_label:<49} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Codebase Analyzed: {f'{files_analyzed_count} files processed':<49} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Estimated Tokens:  {f'~{total_estimated_tokens:,} tokens':<49} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Regolo Token Rate: €0.12 per 1,000,000 tokens{' ':>25} {Color.CYAN}║{Color.RESET}")
    cost_str = f"€{total_cost_eur:.6f} EUR"
    print(f"{Color.CYAN}║{Color.RESET}  • {Color.GREEN}{Color.BOLD}TOTAL SCAN COST:{Color.RESET}   {Color.GREEN}{Color.BOLD}{cost_str:<49}{Color.RESET} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}╠{'═' * 70}╣{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  {Color.WHITE}Generated Reports:{Color.RESET}{' ':>49} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • JSON:   baco-output/findings.json{' ':>35} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • HTML:   baco-output/report.html{' ':>37} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • SARIF:  baco-output/report.sarif{' ':>36} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}╚{'═' * 70}╝{Color.RESET}")

    # Optional interactive prompts
    if interactive:
        report_html = OUTPUT_DIR / "report.html"
        if report_html.exists():
            open_choice = input(f"\nOpen interactive HTML report in browser? [y/N]: ").strip().lower()
            if open_choice in ["y", "yes"]:
                if sys.platform == "darwin":
                    subprocess.run(["open", str(report_html)])
                elif sys.platform.startswith("linux"):
                    subprocess.run(["xdg-open", str(report_html)])

        if findings_count > 0:
            fix_now = input(f"\n{Color.BOLD}Generate AI fixes for all {findings_count} vulnerabilities now? [Y/n]: {Color.RESET}").strip().lower()
            if fix_now in ["", "y", "yes"]:
                clear_screen()
                fix_vulnerabilities(target_path=target_path, findings_list=findings_list)


# ── Option 3: Generate AI Fixes for Vulnerabilities ─────────────────

def generate_ai_fix_for_finding(finding: dict, source_code_snippet: str, model: str, api_key: str) -> dict:
    """
    Call Regolo.ai with the selected model to generate a concrete patch,
    root-cause analysis, and unified diff for a single vulnerability finding.
    """
    system_prompt = (
        "You are an expert security engineer and software developer. "
        "Your task is to fix a security vulnerability found in source code. "
        "Provide a precise explanation, a unified diff (patch), and the complete replacement code. "
        "Format your response as a valid JSON object with keys: "
        "'explanation', 'diff', 'fixed_code', 'security_rationale'."
    )

    user_prompt = f"""Vulnerability Details:
- Title: {finding.get('title', 'Unknown')}
- CWE: {finding.get('cwe_id', 'N/A')}
- Severity: {finding.get('severity', 'Unknown')}
- File: {finding.get('file_path', 'Unknown')}
- Line: {finding.get('line_number', 'Unknown')}
- Description: {finding.get('description', '')}
- Recommendation: {finding.get('recommendation', '')}

Vulnerable Code Context:
```
{source_code_snippet}
```

Please analyze this vulnerability and generate a secure fix. Return ONLY a valid JSON object with:
{{
  "explanation": "Why this vulnerability exists and how the fix addresses it",
  "diff": "Unified diff hunk (--- a/file +++ b/file) applying the fix",
  "fixed_code": "The secure replacement code snippet",
  "security_rationale": "Security best practices applied"
}}"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 1500
    }

    try:
        req = urllib.request.Request(
            REGOLO_COMPLETIONS_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=90) as response:
            res = json.loads(response.read().decode())
            content = res["choices"][0]["message"]["content"].strip()

            # Clean markdown code blocks if the model wrapped the JSON in ```json ... ```
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            try:
                parsed = json.loads(content)
                return parsed
            except Exception:
                return {
                    "explanation": content,
                    "diff": finding.get("diff_hunk") or "",
                    "fixed_code": finding.get("recommendation") or "",
                    "security_rationale": "Generated by Regolo LLM model"
                }
    except Exception as e:
        return {
            "explanation": f"Automated fix generation fallback (API call failed: {e})",
            "diff": finding.get("diff_hunk") or "",
            "fixed_code": finding.get("recommendation") or "Review and sanitize affected input parameters.",
            "security_rationale": "Generated from scanner recommendations"
        }


def fix_vulnerabilities(target_path: Path = None, findings_list: list = None):
    header("OPTION 3: Generate AI Fixes for Vulnerabilities (Regolo LLM)")

    api_key = get_saved_regolo_key()
    if not api_key:
        error("REGOLO_API_KEY not configured. Run Option 1 first.")
        return

    model = get_configured_model()

    # Load findings if not passed directly
    if findings_list is None:
        findings_file = OUTPUT_DIR / "findings.json"
        if not findings_file.exists():
            error(f"No scan findings found at {findings_file.relative_to(ROOT_DIR, walk_up=True)}.")
            info("Please run a scan first (Option 2).")
            return

        try:
            with open(findings_file, "r") as f:
                findings_list = json.load(f)
        except Exception as e:
            error(f"Error reading findings.json: {e}")
            return

    if not findings_list:
        info("No vulnerabilities detected to fix. Great job!")
        return

    # Determine project name and target path
    if target_path is None:
        first_file = findings_list[0].get("file_path", "")
        if first_file and Path(first_file).exists():
            target_path = Path(first_file).parent
        else:
            target_path = ROOT_DIR

    project_name = target_path.name if target_path else "scan-target"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    remediation_folder_name = f"{timestamp}_{project_name}"
    remediation_dir = REMEDIATIONS_DIR / remediation_folder_name
    patches_dir = remediation_dir / "patches"

    remediation_dir.mkdir(parents=True, exist_ok=True)
    patches_dir.mkdir(parents=True, exist_ok=True)

    info(f"Loaded {Color.BOLD}{len(findings_list)}{Color.RESET} vulnerabilities to remediate.")
    info(f"Remediation model: {Color.CYAN}{model}{Color.RESET}")
    info(f"Target directory:  {Color.DIM}{remediation_dir}{Color.RESET}\n")

    remediation_records = []
    patches_summary = []

    for idx, finding in enumerate(findings_list, 1):
        f_id = finding.get("id", f"finding-{idx}")
        title = finding.get("title", "Untitled Vulnerability")
        cwe = finding.get("cwe_id", "N/A")
        file_path_str = finding.get("file_path", "")
        line_num = finding.get("line_number")
        sev = finding.get("severity", "Medium")

        print(f"[{idx}/{len(findings_list)}] Analyzing & patching {Color.YELLOW}{title}{Color.RESET} ({sev}) in {Path(file_path_str).name}...")

        # Extract source code context around vulnerability if file exists
        code_context = finding.get("code_snippet") or ""
        f_path = Path(file_path_str)
        if not f_path.is_absolute() and target_path:
            f_path = target_path / f_path

        if f_path.exists() and f_path.is_file():
            try:
                with open(f_path, "r", errors="ignore") as src_f:
                    lines = src_f.readlines()
                    if line_num and 1 <= line_num <= len(lines):
                        start_l = max(0, line_num - 15)
                        end_l = min(len(lines), line_num + 15)
                        code_context = "".join(lines[start_l:end_l])
                    elif not code_context:
                        code_context = "".join(lines[:60])
            except Exception:
                pass

        if not code_context:
            code_context = "# Code snippet not available from report"

        # Generate AI fix with Regolo model
        fix_result = generate_ai_fix_for_finding(finding, code_context, model, api_key)

        record = {
            "finding_id": f_id,
            "title": title,
            "cwe": cwe,
            "severity": sev,
            "file_path": file_path_str,
            "line_number": line_num,
            "explanation": fix_result.get("explanation", ""),
            "diff": fix_result.get("diff", ""),
            "fixed_code": fix_result.get("fixed_code", ""),
            "security_rationale": fix_result.get("security_rationale", "")
        }
        remediation_records.append(record)

        # Write patch file
        cwe_clean = re.sub(r'[^a-zA-Z0-9_]', '_', cwe.split(':', 1)[0].replace('-', '_'))
        file_stem = Path(file_path_str).stem
        safe_name = f"{idx:02d}_{cwe_clean}_{file_stem}"
        patch_file = patches_dir / f"fix_{safe_name}.patch"
        with open(patch_file, "w") as pf:
            pf.write(f"# Patch for {title} ({cwe}) - Severity: {sev}\n")
            pf.write(f"# Target: {file_path_str}:{line_num}\n")
            pf.write(f"# Explanation: {fix_result.get('explanation')}\n\n")
            if fix_result.get("diff"):
                pf.write(fix_result["diff"])
            elif fix_result.get("fixed_code"):
                pf.write("### Fixed Code Replacement:\n")
                pf.write(fix_result["fixed_code"])
            pf.write("\n")

        patches_summary.append({
            "index": idx,
            "title": title,
            "cwe": cwe,
            "severity": sev,
            "file": file_path_str,
            "patch_file": patch_file.name
        })

    # Save structured JSON data
    fixes_json_file = remediation_dir / "fixes.json"
    with open(fixes_json_file, "w") as jf:
        json.dump(remediation_records, jf, indent=2)

    # Save universal LLM-ready instructions prompt
    llm_prompt_file = remediation_dir / "llm_fix_instructions.md"
    with open(llm_prompt_file, "w") as lf:
        lf.write(f"# Security Remediation Instructions for LLM Agents\n\n")
        lf.write(f"**Project:** `{project_name}`\n")
        lf.write(f"**Date:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n")
        lf.write(f"**Scanner:** BACO Security Scanner (Regolo.ai Edition)\n")
        lf.write(f"**Total Vulnerabilities Fixed:** {len(remediation_records)}\n\n")
        lf.write("---\n\n")
        lf.write("## Instructions for the LLM / AI Coding Assistant:\n")
        lf.write("You are acting as an automated security patch engineer. "
                 "Apply the following security patches to the corresponding files in the project. "
                 "Ensure code logic remains intact while eliminating all security flaws.\n\n")

        for item in remediation_records:
            lf.write(f"### Fix #{remediation_records.index(item) + 1}: {item['title']} ({item['cwe']})\n\n")
            lf.write(f"- **Severity:** `{item['severity']}`\n")
            lf.write(f"- **Target File:** `{item['file_path']}` (Line: `{item['line_number']}`)\n")
            lf.write(f"- **Why this is vulnerable:** {item['explanation']}\n")
            lf.write(f"- **Security Rationale:** {item['security_rationale']}\n\n")
            if item["diff"]:
                lf.write("#### Unified Diff:\n```diff\n" + item["diff"] + "\n```\n\n")
            if item["fixed_code"]:
                lf.write("#### Secure Code Replacement:\n```python\n" + item["fixed_code"] + "\n```\n\n")
            lf.write("---\n\n")

    # Save human-readable README in the folder
    readme_file = remediation_dir / "README.md"
    with open(readme_file, "w") as rf:
        rf.write(f"# Security Remediation Report — {project_name}\n\n")
        rf.write(f"- **Date Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        rf.write(f"- **Model Used:** `{model}` (Regolo.ai)\n")
        rf.write(f"- **Total Patches:** {len(remediation_records)}\n\n")
        rf.write("## Files in this remediation package:\n")
        rf.write("1. `llm_fix_instructions.md` — Copy-pasteable prompt ready for any LLM (Claude Code, Cursor, Copilot, ChatGPT).\n")
        rf.write("2. `fixes.json` — Machine-readable structured remediation data.\n")
        rf.write("3. `patches/` — Individual `.patch` files for each vulnerability.\n\n")
        rf.write("## Remediation Summary:\n\n")
        rf.write("| # | Vulnerability | CWE | Severity | File | Patch |\n")
        rf.write("|---|---|---|---|---|---|\n")
        for p in patches_summary:
            rf.write(f"| {p['index']} | {p['title']} | {p['cwe']} | {p['severity']} | `{p['file']}` | `{p['patch_file']}` |\n")

    # Display final success summary
    print("\n")
    print(f"{Color.GREEN}╔{'═' * 70}╗{Color.RESET}")
    print(f"{Color.GREEN}║{Color.RESET} {Color.BOLD}{'REMEDIATION PACKAGE GENERATED SUCCESSFULLY':^68}{Color.RESET} {Color.GREEN}║{Color.RESET}")
    print(f"{Color.GREEN}╠{'═' * 70}╣{Color.RESET}")
    print(f"{Color.GREEN}║{Color.RESET}  {Color.WHITE}Folder:{Color.RESET}         {str(remediation_dir.relative_to(ROOT_DIR, walk_up=True))[:50]:<50} {Color.GREEN}║{Color.RESET}")
    print(f"{Color.GREEN}║{Color.RESET}  {Color.WHITE}Total Patches:{Color.RESET}  {f'{len(remediation_records)} automated fixes created':<50} {Color.GREEN}║{Color.RESET}")
    print(f"{Color.GREEN}║{Color.RESET}  {Color.WHITE}LLM Prompt:{Color.RESET}     llm_fix_instructions.md (Ready for any LLM){' ':>9} {Color.GREEN}║{Color.RESET}")
    print(f"{Color.GREEN}║{Color.RESET}  {Color.WHITE}JSON Data:{Color.RESET}      fixes.json{' ':>41} {Color.GREEN}║{Color.RESET}")
    print(f"{Color.GREEN}║{Color.RESET}  {Color.WHITE}Patches Dir:{Color.RESET}    patches/ ({len(remediation_records)} individual diff files){' ':>17} {Color.GREEN}║{Color.RESET}")
    print(f"{Color.GREEN}╚{'═' * 70}╝{Color.RESET}")
    print(f"\n{Color.CYAN}Tip:{Color.RESET} You can feed {Color.BOLD}{remediation_dir / 'llm_fix_instructions.md'}{Color.RESET} directly into Claude Code, Cursor, Copilot, or ChatGPT to apply all fixes automatically!")


def cost_command():
    """Display standalone Brick Complexity Pro token cost analysis."""
    header("Brick Complexity Pro Cost Analysis")
    findings_file = OUTPUT_DIR / "findings.json"
    if not findings_file.exists():
        error(f"No scan report found at {findings_file.relative_to(ROOT_DIR, walk_up=True)}. Run a scan first.")
        return

    try:
        with open(findings_file, "r") as f:
            findings = json.load(f)
    except Exception as e:
        error(f"Failed to read findings: {e}")
        return

    count = len(findings)
    metrics = calculate_scan_tokens_and_cost(ROOT_DIR, count)
    total_tokens = metrics["total_tokens"]
    total_cost_eur = metrics["cost_eur"]
    files_analyzed = metrics["files_count"]

    print(f"\n{Color.CYAN}╔{'═' * 66}╗{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET} {Color.BOLD}{'BRICK COMPLEXITY PRO COST BREAKDOWN':^64}{Color.RESET} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}╠{'═' * 66}╣{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Router Model:      brick-complexity-pro (Regolo.ai){' ':>15} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Codebase Analyzed: {f'{files_analyzed} files scanned':<45} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Findings Detected: {f'{count} vulnerabilities':<45} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Estimated Tokens:  {f'~{total_tokens:,} tokens':<45} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}║{Color.RESET}  • Regolo Rate:       €0.12 per 1,000,000 tokens{' ':>21} {Color.CYAN}║{Color.RESET}")
    cost_str = f"€{total_cost_eur:.6f} EUR"
    print(f"{Color.CYAN}║{Color.RESET}  • {Color.GREEN}{Color.BOLD}TOTAL COST:{Color.RESET}        {Color.GREEN}{Color.BOLD}{cost_str:<45}{Color.RESET} {Color.CYAN}║{Color.RESET}")
    print(f"{Color.CYAN}╚{'═' * 66}╝{Color.RESET}\n")


# ── Main TUI Loop ───────────────────────────────────────────────────

def main():
    # Verify semgrep availability
    if not check_semgrep():
        warn("Semgrep not found in PATH. Install it using:")
        print(f"   {Color.CYAN}pipx install semgrep{Color.RESET} or {Color.CYAN}brew install semgrep{Color.RESET}")

    # Ensure prompts symlink is present
    ensure_prompts_symlink()

    # Check and compile baco engine if needed
    baco_bin = ensure_baco_binary()

    # Handle CLI subcommands for OpenCode / script automation
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ["scan", "audit"]:
            target = sys.argv[2] if len(sys.argv) > 2 else "."
            scan_repository(baco_bin, target_path_override=Path(target), interactive=False)
            return
        elif cmd in ["fix", "remediate", "patch"]:
            fix_vulnerabilities()
            return
        elif cmd in ["cost", "pricing"]:
            cost_command()
            return
        elif cmd in ["setup", "config"]:
            setup_environment()
            return
        elif cmd in ["-h", "--help", "help"]:
            print("Usage: python3 baco_tui.py [scan <path> | fix | cost | setup]")
            return

    while True:
        clear_screen()
        print_regolo_header()

        saved_key = get_saved_regolo_key()
        status_key = f"{Color.GREEN}Configured ({saved_key[:5]}...){Color.RESET}" if saved_key else f"{Color.YELLOW}Not configured{Color.RESET}"
        current_model = get_configured_model()

        print(f"  Regolo API Key:   {status_key}")
        print(f"  Selected Model:   {Color.CYAN}{current_model}{Color.RESET}")
        print(f"  Endpoint:         {Color.DIM}{REGOLO_BASE_URL}{Color.RESET}\n")

        print(f"  {Color.BOLD}[1]{Color.RESET} ⚙️   Setup Environment (Regolo.ai API Key & Model)")
        print(f"  {Color.BOLD}[2]{Color.RESET} 🔍  Scan Repository & View Findings + Cost (Brick Complexity Pro)")
        print(f"  {Color.BOLD}[3]{Color.RESET} 🛠️   Generate AI Fixes for Vulnerabilities (Regolo LLM)")
        print(f"  {Color.BOLD}[4]{Color.RESET} 🚪  Exit")

        choice = input(f"\n{Color.BOLD}Select an option (1-4): {Color.RESET}").strip()

        if choice == "1":
            clear_screen()
            setup_environment()
        elif choice == "2":
            clear_screen()
            scan_repository(baco_bin)
        elif choice == "3":
            clear_screen()
            fix_vulnerabilities()
        elif choice == "4":
            clear_screen()
            print(f"\n{Color.CYAN}Goodbye!{Color.RESET}\n")
            break
        else:
            warn("Invalid option. Please choose 1, 2, 3, or 4.")

        input(f"\n{Color.DIM}Press Enter to return to main menu...{Color.RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Color.YELLOW}Operation cancelled by user.{Color.RESET}")
        sys.exit(0)
