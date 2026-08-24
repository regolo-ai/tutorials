"""Main CLI entrypoint for Regolo Deep Agents with Brick Semantic Routing.
Supports interactive green TUI mode and automated headless execution.
"""

import argparse
import os
import sys
from pathlib import Path

import config
from core.docker_manager import get_services_status, start_all_services
from core.orchestrator import DeepAgentOrchestrator
from core.regolo_client import RegoloClient
from core.sandbox import SandboxEnvironment
from tui import (
    display_brick_routing_matrix,
    display_telemetry_scoreboard,
    interactive_main_menu,
    print_regolo_banner,
)


def run_headless_auto(target_path: str, goal: str):
    """Execute non-interactive automated pipeline run."""
    print_regolo_banner()
    print(f"[*] Initializing Headless Deep Agents Pipeline on: {target_path}")
    print(f"[*] Goal: {goal}\n")

    sandbox = SandboxEnvironment(source_repo_path=target_path)
    orchestrator = DeepAgentOrchestrator()

    def stdout_logger(agent_tag: str, msg: str):
        print(f"[{agent_tag}] {msg}")

    result = orchestrator.run_pipeline(
        sandbox=sandbox,
        goal=goal,
        log_callback=stdout_logger,
        human_approval_callback=None,
    )

    print("\n" + "=" * 60)
    print(f"[✔] Pipeline Status: {result.get('status')}")
    print(f"[✔] Total Duration: {result.get('duration_sec')}s")
    print(f"[✔] Spec Output: {result.get('report_file')}")
    print("=" * 60 + "\n")

    display_telemetry_scoreboard()


def main():
    parser = argparse.ArgumentParser(
        description="Regolo Deep Agents: Multi-Agent Tool Synthesis with Brick Semantic Routing"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run in headless automated mode without interactive prompts",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=str(config.SAMPLE_REPOS_DIR / "ai_tool_nexus"),
        help="Path to repository target for MCP tool synthesis",
    )
    parser.add_argument(
        "--goal",
        type=str,
        default="Synthesize production FastMCP tool harness with Pydantic V2 schemas and tests",
        help="Synthesis goal description",
    )
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Display the Brick Semantic Routing matrix and exit",
    )
    parser.add_argument(
        "--services",
        action="store_true",
        help="Start all Docker background services and exit",
    )

    args = parser.parse_args()

    if args.services:
        print("[*] Launching Docker services with incremental port discovery...")
        results = start_all_services(log_callback=lambda m: print(f"  {m}"))
        print("[✔] Service deployment complete.")
        return

    if args.matrix:
        display_brick_routing_matrix()
        return

    if args.auto:
        run_headless_auto(args.target, args.goal)
    else:
        interactive_main_menu()


if __name__ == "__main__":
    main()
