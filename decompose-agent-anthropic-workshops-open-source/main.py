import sys
import json
import os
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
REGOLO_MODELS_URL = "https://api.regolo.ai/v1/models"
REGOLO_SIGNUP_URL = "https://regolo.ai/pricing"


# ---------------------------------------------------------------------------
# Helpers — menu and setup
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    print("\n" + "=" * 52)
    print("   StockPilot — Decomposed Agent (Anthropic style)")
    print("=" * 52)


def _choose_provider() -> str:
    """Returns 'ollama' or 'regolo'."""
    print("\n  Select LLM provider:\n")
    print("  [1] OLLAMA  — local, no API key required")
    print("  [2] Regolo  — cloud GPU, free API key\n")
    while True:
        choice = input("  Choice [1/2]: ").strip()
        if choice == "1":
            return "ollama"
        if choice == "2":
            return "regolo"
        print("  Invalid input. Enter 1 or 2.")


def _load_env_key() -> str:
    """Reads REGOLO_API_KEY from the .env file. Returns an empty string if not found."""
    if not os.path.exists(ENV_FILE):
        return ""
    api_key = ""
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("REGOLO_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
    return api_key


def _save_env_key(api_key: str) -> None:
    """Writes (or updates) REGOLO_API_KEY in the .env file."""
    lines = []
    key_written = False
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()
        lines = [
            (f"REGOLO_API_KEY={api_key}\n" if l.startswith("REGOLO_API_KEY=") else l)
            for l in lines
        ]
        key_written = any(l.startswith("REGOLO_API_KEY=") for l in lines)
    if not key_written:
        lines.append(f"REGOLO_API_KEY={api_key}\n")
    with open(ENV_FILE, "w") as f:
        f.writelines(lines)


def _fetch_regolo_models(api_key: str) -> list[str]:
    """Fetches the model list from the Regolo endpoint."""
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(REGOLO_MODELS_URL, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    return [m["id"] for m in data.get("data", [])]


def _choose_model(models: list[str]) -> str:
    """Displays the model list and prompts the user to pick one."""
    print("\n  Available models on Regolo:\n")
    for i, model in enumerate(models, 1):
        print(f"  [{i:>2}] {model}")
    print()
    while True:
        choice = input(f"  Select a model [1-{len(models)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice) - 1]
        print("  Invalid input.")


def setup_regolo() -> tuple[str, str]:
    """
    Guides the user through Regolo setup:
      1. Checks / creates the .env file with the API key
      2. Fetches available models
      3. Prompts the user to select a model
      4. Waits for confirmation before proceeding
    Returns (api_key, model_name).
    """
    api_key = _load_env_key()

    if not api_key:
        print("\n" + "─" * 52)
        print("  Regolo API key not found.\n")
        print("  Sign up for free at:")
        print(f"  → {REGOLO_SIGNUP_URL}")
        print("  (click 'Pay as You Go' to start for free)\n")
        print("─" * 52)
        api_key = input("\n  Paste your Regolo API key here: ").strip()
        if not api_key:
            print("\n  No API key provided. Exiting.")
            sys.exit(1)
        _save_env_key(api_key)
        print(f"\n  ✓ API key saved to {ENV_FILE}")
    else:
        print(f"\n  ✓ API key loaded from {ENV_FILE}")

    print("\n  Fetching available models…")
    try:
        models = _fetch_regolo_models(api_key)
    except Exception as e:
        print(f"\n  Error fetching models: {e}")
        sys.exit(1)

    if not models:
        print("\n  No models available. Check your API key.")
        sys.exit(1)

    model = _choose_model(models)

    print("\n" + "─" * 52)
    print(f"  Provider : Regolo")
    print(f"  Model    : {model}")
    print("─" * 52)
    confirm = input("\n  Press ENTER to start the tests (q + ENTER to quit): ").strip().lower()
    if confirm == "q":
        sys.exit(0)

    return api_key, model


def setup_ollama() -> str:
    """Prompts for the Ollama model to use (default: llama3)."""
    default_model = "llama3"
    print(f"\n  Ollama model to use [{default_model}]: ", end="")
    model = input().strip() or default_model
    print("\n" + "─" * 52)
    print(f"  Provider : Ollama (local)")
    print(f"  Model    : {model}")
    print("─" * 52)
    confirm = input("\n  Press ENTER to start the tests (q + ENTER to quit): ").strip().lower()
    if confirm == "q":
        sys.exit(0)
    return model


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------


def run_e2e_tests() -> None:
    from agent.orchestrator import StockPilotOrchestrator

    print("\n" + "=" * 52)
    print("  Starting E2E Tests for StockPilot (Decomposed)")
    print("=" * 52)

    orchestrator = StockPilotOrchestrator()

    # ------------------------------------------------------------------
    print("\n[TEST 1] Testing F1: Low Stock Sweep via Python Code execution…")
    query_f1 = "Run the daily low-stock sweep and identify which items require a replenishment order."

    try:
        response_f1 = orchestrator.route_and_execute(query_f1)
        print("Raw Agent Output:")
        print(response_f1)

        assert "SKU-0116" in response_f1, "SKU-0116 should be identified as low stock."
        assert "SKU-0300" in response_f1, "SKU-0300 should be identified as low stock."
        assert "SKU-0200" not in response_f1, "SKU-0200 has sufficient stock and should not be listed."
        print(">>> [TEST 1] SUCCESSFUL: Low-stock identified accurately via code primitive.")
    except AssertionError as e:
        print(f">>> [TEST 1] FAILED: {str(e)}")
    except Exception as e:
        print(f">>> [TEST 1] FAILED with unexpected error: {str(e)}")

    # ------------------------------------------------------------------
    print("\n[TEST 2] Testing R8: Promotional Month Demand Forecast…")
    query_r8 = "Generate the demand forecast for SKU-0116 during the promo month of October (30 days)."

    try:
        response_r8 = orchestrator.route_and_execute(query_r8)
        print("Raw Agent Output:")
        print(response_r8)

        clean_json_str = response_r8.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json_str)

        expected_demand = 12 * 30 * 3.1
        actual_demand = float(data.get("forecasted_demand", 0))

        print(f"Expected computed demand: {expected_demand} units.")
        print(f"Agent computed demand: {actual_demand} units.")

        assert abs(actual_demand - expected_demand) < 0.1, (
            f"Forecast error. Expected {expected_demand}, got {actual_demand}."
        )
        print(">>> [TEST 2] SUCCESSFUL: Subagent correctly computed the promo multiplier without prompt leakage.")
    except AssertionError as e:
        print(f">>> [TEST 2] FAILED: {str(e)}")
    except json.JSONDecodeError:
        print(">>> [TEST 2] FAILED: Output was not valid JSON.")
    except Exception as e:
        print(f">>> [TEST 2] FAILED with unexpected error: {str(e)}")

    print("\n" + "=" * 52)
    print("  E2E Test Session Concluded.")
    print("=" * 52 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import agent.llm_client as llm_client

    _print_banner()
    provider = _choose_provider()

    if provider == "ollama":
        model = setup_ollama()
        llm_client.configure(backend="ollama", model=model)
    else:
        api_key, model = setup_regolo()
        llm_client.configure(backend="regolo", model=model, api_key=api_key)

    run_e2e_tests()