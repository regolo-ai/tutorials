import getpass
import os
import sys
import requests

from src.agent import LiveSessionAgent
from src.console import Style, error, file_list, info, key_value, paint, panel, step, success, warning
from src.dream import DreamingOrchestrator

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

# ---------------------------------------------------------------------------
# Menu helpers
# ---------------------------------------------------------------------------

def print_banner(title: str):
    panel(title, [], Style.CYAN)


def choose_provider() -> str:
    panel(
        "Memory Agent - Select LLM Provider",
        [
            f"{paint('[1]', Style.GREEN, Style.BOLD)} OLLAMA  {paint('local, no API key required', Style.DIM)}",
            f"{paint('[2]', Style.MAGENTA, Style.BOLD)} Regolo {paint('cloud inference, free with API key', Style.DIM)}",
        ],
        Style.CYAN,
    )
    while True:
        choice = input(paint("Enter 1 or 2: ", Style.BOLD)).strip()
        if choice in ("1", "2"):
            return choice
        warning("Invalid choice. Enter 1 or 2.")


def fetch_regolo_models() -> list[str]:
    info("Fetching models from api.regolo.ai...")
    try:
        resp = requests.get("https://api.regolo.ai/v1/models", timeout=10)
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        success(f"Loaded {len(models)} models")
        return models
    except Exception as e:
        error(f"Could not fetch Regolo models: {e}")
        sys.exit(1)


def choose_model(models: list[str]) -> str:
    print(f"\n  {paint('Available models on Regolo:', Style.BOLD)}\n")
    for i, m in enumerate(models, 1):
        print(f"    {paint(f'[{i:>2}]', Style.MAGENTA, Style.BOLD)} {m}")
    print()
    while True:
        choice = input(paint(f"  Choose a model (1-{len(models)}): ", Style.BOLD)).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice) - 1]
        warning(f"Invalid choice. Enter a number between 1 and {len(models)}.")


def setup_env_and_get_key() -> str:
    """
    If a valid .env already exists, reads and returns the stored key.
    Otherwise, shows registration instructions, prompts the user to paste
    their API key directly in the terminal, writes the .env file, and
    returns the key.
    """
    env_abs = os.path.abspath(ENV_FILE)

    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("REGOLO_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    if key and key != "your_api_key_here":
                        success(f"API key loaded from {env_abs}")
                        return key

    panel(
        "API Key Setup - Regolo",
        [
            "To get your FREE API key:",
            "",
            "1. Go to https://regolo.ai/pricing",
            "2. Click \"Pay as You Go\"",
            "3. Sign up (free, no credit card required)",
            "4. Copy your API key from the dashboard",
        ],
        Style.MAGENTA,
    )

    while True:
        key = getpass.getpass("  Paste your REGOLO_API_KEY here: ").strip()
        if key and key != "your_api_key_here":
            break
        warning("Invalid key. Please paste a valid API key.")

    with open(ENV_FILE, "w") as f:
        f.write(f"REGOLO_API_KEY={key}\n")

    success(f".env file created at {env_abs}")
    return key


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(llm):
    step(2, "Live session", "Index-first memory loading + write-through session note")
    agent = LiveSessionAgent(memory_dir="data/input_memory", llm=llm)

    response = agent.execute_session("Show me what you know about the CWC 2026 conference.")
    success("Agent response generated")
    file_list("Context files loaded", agent.last_loaded_files)
    panel("Agent Response", response.splitlines() or [response], Style.GREEN)

    step(3, "Dream cycle", "Consolidating transcripts and materializing a clean output store")
    dreamer = DreamingOrchestrator(
        input_store="data/input_memory",
        transcripts_dir="data/transcripts",
        output_store="data/output_memory",
        llm=llm,
    )
    status = dreamer.run_dream_cycle()
    success(status["status"])
    file_list("Files written", status["files_written"])
    if status["diff_available"]:
        info("Human review diff available at data/output_memory/_review.diff")

    panel(
        "Pipeline Complete",
        [
            "Live memory was read selectively.",
            "A session note was appended to data/input_memory/sessions.md.",
            "A consolidated memory store was written to data/output_memory/.",
        ],
        Style.GREEN,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    provider = choose_provider()

    if provider == "1":
        # ── OLLAMA ──────────────────────────────────────────────────────────
        from src.llm import LocalLLM
        step(1, "Initializing Local LLM", "Ollama with deterministic mock fallback")
        llm = LocalLLM()
        run_pipeline(llm)

    else:
        # ── REGOLO ──────────────────────────────────────────────────────────
        from src.llm import RegoloLLM

        models = fetch_regolo_models()
        model_name = choose_model(models)
        key_value("Selected model", paint(model_name, Style.MAGENTA, Style.BOLD))

        api_key = setup_env_and_get_key()
        step(1, "Initializing Regolo LLM", f"Model: {model_name}")

        llm = RegoloLLM(model_name=model_name, api_key=api_key)
        run_pipeline(llm)

