"""
main.py
-------
Enterprise closed-loop code review system.
Pipeline: Ingest -> Retrieve -> Rerank -> Generate -> Verify -> Execute -> Feedback
"""
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

from openai import OpenAI

from src.config import load_env_file, PricingConfig, Settings
from src.orchestrator import ReviewOrchestrator
from src.utils import prompt_text, prompt_float

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("closed_loop")

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "review_output"
SRC_DIR = ROOT / "src_to_review"
TARGET_FILE = SRC_DIR / "math_service.py"

OUTPUT_DIR.mkdir(exist_ok=True)
SRC_DIR.mkdir(exist_ok=True)

ASCII_BANNER = """\033[0;32m
██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗      █████╗ ██╗
██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗    ██╔══██╗██║
██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║    ███████║██║
██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║    ██╔══██║██║
██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝    ██║  ██║██║
╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝     ╚═╝  ╚═╝╚═╝\033[0m

      C O D E   R E V I E W E R   ·   E N T E R P R I S E
"""


def print_menu() -> None:
    print(ASCII_BANNER)
    print("=" * 78)
    print("Enterprise closed-loop code review with Qdrant retrieval + Qwen3 reranker")
    print("=" * 78)
    print("1) Run demo on sample buggy file")
    print("2) Run on custom target file")
    print("3) Exit")
    print()


def build_client(settings: Settings) -> OpenAI:
    load_env_file()
    api_key = os.environ.get("REGOLO_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("Missing REGOLO_API_KEY. Set it in .env or environment.")
    return OpenAI(api_key=api_key, base_url=settings.base_url)


def configure_pricing(settings: Settings) -> PricingConfig:
    print("\nCost model setup")
    input_cost = prompt_float("Input token cost per 1K tokens (USD)", settings.default_input_cost_per_1k)
    output_cost = prompt_float("Output token cost per 1K tokens (USD)", settings.default_output_cost_per_1k)
    return PricingConfig(input_cost_per_1k=input_cost, output_cost_per_1k=output_cost)


def run_app() -> None:
    load_env_file()
    settings = Settings.from_env()
    print_menu()
    choice = prompt_text("Choose an option", "1")
    if choice == "3":
        print("Goodbye.")
        return

    pricing = configure_pricing(settings)
    client = build_client(settings)

    if choice == "2":
        raw_path = prompt_text("Enter path to Python file or folder to review", str(TARGET_FILE))
        cleaned_path = raw_path.strip().strip("'\"").strip()
        custom_path = Path(cleaned_path).expanduser()
        if not custom_path.exists():
            raise FileNotFoundError(f"Target path does not exist: {custom_path}")
        target = custom_path
    else:
        target = TARGET_FILE

    if target.is_dir():
        print(f"\nScanning directory: {target}")
        py_files = []
        skip_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist"}
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for file in files:
                if file.endswith(".py"):
                    py_files.append(Path(root) / file)

        if not py_files:
            print(f"No Python (.py) files found in {target}.")
            return

        print(f"Found {len(py_files)} Python file(s) to review:")
        for f in py_files:
            print(f"  - {f.relative_to(target) if target in f.parents else f}")

        start_folder_time = time.time()
        results = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_estimated_cost = 0.0

        for i, file_path in enumerate(py_files, 1):
            print("\n" + "=" * 78)
            print(f"REVIEWING FILE [{i}/{len(py_files)}]: {file_path}")
            print("=" * 78)
            try:
                orchestrator = ReviewOrchestrator(client=client, pricing=pricing, settings=settings, target_file=file_path)
                res = orchestrator.run()
                results.append((file_path, res))
                
                usage = res.get("usage", {})
                total_prompt_tokens += usage.get("total_prompt_tokens", 0)
                total_completion_tokens += usage.get("total_completion_tokens", 0)
                total_estimated_cost += usage.get("total_estimated_cost_usd", 0.0)
            except Exception as e:
                logger.error(f"Error reviewing {file_path}: {e}")
                results.append((file_path, {"status": "ERROR", "verifier_reason": str(e)}))

        total_folder_duration = time.time() - start_folder_time

        reset = "\033[0m"
        bold = "\033[1m"
        cyan = "\033[1;36m"
        yellow = "\033[1;33m"
        green = "\033[1;32m"
        red = "\033[1;31m"

        print("\n" + "╔" + "═" * 76 + "╗")
        print(f"║ {cyan}CLOSED-LOOP FOLDER REVIEW SUMMARY{reset} ".ljust(86) + "║")
        print("╠" + "═" * 76 + "╣")
        print(f"║  {bold}Total Files Scanned:{reset} {len(py_files):<53} ║")
        print("╠" + "═" * 76 + "╣")
        
        success_count = 0
        failed_count = 0
        error_count = 0

        for file_path, res in results:
            status = res.get("status", "UNKNOWN")
            reason = res.get("verifier_reason", "")
            rel_path = file_path.relative_to(target) if target in file_path.parents else file_path
            
            if status == "SUCCESS":
                color = "\033[1;92m"
                status_icon = "✅"
                success_count += 1
            elif status == "ERROR":
                color = "\033[1;91m"
                status_icon = "⚠️"
                error_count += 1
            else:
                color = "\033[1;91m"
                status_icon = "❌"
                failed_count += 1
                
            line_str = f"  {status_icon} [{color}{status}{reset}] {rel_path}"
            if reason:
                line_str += f" - Reason: {reason}"
            # Format and print with margins
            print(f"║ {line_str:<85}".replace(color, "").replace(reset, "")[:76].ljust(76) + "║")
            # Actually print with colors to the terminal
            # (using raw prints below the box or inside the box manually)

        # To keep box layout pristine and robust, we print the details inside:
        print("╠" + "═" * 76 + "╣")
        print(f"║ {cyan}AGGREGATED METRICS{reset} ".ljust(86) + "║")
        print("╠" + "═" * 76 + "╣")
        print(f"║  {bold}Succeeded:{reset} {green}{success_count:<58}{reset} ║")
        print(f"║  {bold}Failed:{reset} {red}{failed_count:<61}{reset} ║")
        if error_count:
            print(f"║  {bold}Errors:{reset} {red}{error_count:<61}{reset} ║")
        
        print(f"║  {bold}Total Cost:{reset} {green}${total_estimated_cost:.4f}{reset}".ljust(85) + "║")
        print(f"║  {bold}Total Prompt Tokens:{reset} {total_prompt_tokens:,}".ljust(85) + "║")
        print(f"║  {bold}Total Completion Tokens:{reset} {total_completion_tokens:,}".ljust(85) + "║")
        print(f"║  {bold}Total Duration:{reset} {yellow}{total_folder_duration:.2f}s{reset}".ljust(85) + "║")
        
        print("╠" + "═" * 76 + "╣")
        print(f"║ {cyan}EFFICIENCY METRICS (vs. Human Dev Team @ $50/hr & 4h/file cycle){reset} ".ljust(86) + "║")
        print("╠" + "═" * 76 + "╣")
        
        # Benchmark definitions for folder
        num_files = len(py_files)
        HUMAN_COST = 200.0 * num_files  # 4 hours @ $50/hr per file
        HUMAN_TIME = 14400.0 * num_files  # 4 hours in seconds per file
        
        cost_saved = max(0.0, HUMAN_COST - total_estimated_cost)
        cost_saved_pct = (cost_saved / HUMAN_COST) * 100 if HUMAN_COST > 0 else 0.0
        time_saved = max(0.0, HUMAN_TIME - total_folder_duration)
        time_saved_pct = (time_saved / HUMAN_TIME) * 100 if HUMAN_TIME > 0 else 0.0
        
        print(f"║  🚀 {bold}Cost Savings:{reset} {green}{cost_saved_pct:.2f}%{reset} (${cost_saved:.2f} saved)".ljust(85) + "║")
        print(f"║  ⏱️  {bold}Time Savings:{reset} {green}{time_saved_pct:.2f}%{reset} ({time_saved/3600:.2f} hours faster)".ljust(85) + "║")
        
        overall_speedup = HUMAN_TIME / max(0.1, total_folder_duration)
        print(f"║  🔥 {bold}Speedup Factor:{reset} {yellow}{overall_speedup:.1f}x{reset} faster completion time".ljust(85) + "║")
        print("╚" + "═" * 76 + "╝")

        # Save aggregated results
        agg_summary_path = OUTPUT_DIR / "folder_review_summary.json"
        agg_payload = {
            "target_folder": str(target),
            "files_scanned": len(py_files),
            "summary": {
                "success_count": success_count,
                "failed_count": failed_count,
                "error_count": error_count,
                "total_estimated_cost_usd": round(total_estimated_cost, 6),
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
            },
            "files": [
                {
                    "file": str(fp),
                    "status": r.get("status"),
                    "verifier_reason": r.get("verifier_reason"),
                }
                for fp, r in results
            ]
        }
        agg_summary_path.write_text(json.dumps(agg_payload, indent=2), encoding="utf-8")
        print(f"\nFolder review audit details saved to: {agg_summary_path}")

    else:
        orchestrator = ReviewOrchestrator(client=client, pricing=pricing, settings=settings, target_file=target)
        result = orchestrator.run()

        print("\n" + "=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        orchestrator.format_result(result)
        print(f"\nAudit: {OUTPUT_DIR / 'review_audit.json'}")
        print(f"Summary: {OUTPUT_DIR / 'review_summary.json'}")


if __name__ == "__main__":
    try:
        run_app()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Fatal error: %s", exc)
        sys.exit(1)
