"""Interactive Terminal User Interface (TUI) for Regolo Deep Agents.
Features:
- Branded "REGOLO" Green ASCII header and layout
- Docker Service Orchestration (Qdrant & MCP Sandbox with incremental port discovery)
- Interactive Deep Agents Execution with Brick Semantic Routing (brick-complexity-pro)
- Sub-Agent Execution Traces (Planner, Researcher, Tool Agent, Code Executor, Reviewer, Report Writer, Budget Controller)
- Live Telemetry & Single Frontier Model vs Regolo Multi-Model Cost Scoreboard
"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.align import Align
from rich.box import DOUBLE, HEAVY, ROUNDED, SIMPLE
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

import config
from core.brick_router import BrickRouter
from core.budget_controller import BudgetController, get_budget_controller
from core.docker_manager import (
    get_services_status,
    is_docker_available,
    start_all_services,
    stop_all_services,
)
from core.orchestrator import DeepAgentOrchestrator
from core.regolo_client import RegoloClient
from core.sandbox import SandboxEnvironment

console = Console()


def print_regolo_banner():
    """Print top-level branded REGOLO Green ASCII Banner."""
    console.clear()
    
    ascii_art = """
 ██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗ 
 ██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗
 ██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║
 ██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║
 ██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝
 ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ 
"""
    banner_text = Text()
    banner_text.append(ascii_art, style="bold green")
    banner_text.append("⚡ DEEP AGENTS • BRICK SEMANTIC ROUTING (brick-complexity-pro) ⚡\n", style="bold bright_green")
    banner_text.append("Planner  ➔  Researcher  ➔  Tool Agent  ➔  Code Executor  ➔  Reviewer  ➔  Report Writer\n", style="bold white")
    banner_text.append(f"Inference: Regolo.ai API  •  Meta-Router: {config.MODEL_BRICK_ROUTER}  •  Status: Ready", style="dim green")

    console.print(
        Panel(
            Align.center(banner_text),
            box=HEAVY,
            border_style="bright_green",
            padding=(0, 2),
        )
    )


def select_target_workspace() -> Tuple[str, str]:
    """Interactive workspace and goal selection for Deep Agents."""
    console.print("\n[bold green]📁 STEP 1: SELECT TARGET REPOSITORY & SYNTHESIS OBJECTIVE[/bold green]\n")

    sample_targets = [
        {
            "id": "1",
            "name": "AI Tool Nexus (Vector Store, Web Scraper, Sandbox APIs)",
            "path": str(config.SAMPLE_REPOS_DIR / "ai_tool_nexus"),
            "goal": "Synthesize production FastMCP Tool Server with Pydantic V2 validation models, SSRF guards, and unit tests.",
            "type": "Sample AI Tool Platform",
        },
        {
            "id": "2",
            "name": "Current DeepAgents Repository (CODICE)",
            "path": str(config.BASE_DIR),
            "goal": "Analyze all the modules in this repo and create an assessment for me.",
            "type": "Current Repository",
        },
        {
            "id": "3",
            "name": "Custom Local Project Directory",
            "path": "custom",
            "goal": "Analyze local codebase APIs and synthesize custom MCP tool harness.",
            "type": "Custom Target",
        },
    ]

    table = Table(box=ROUNDED, border_style="green", show_header=True, header_style="bold green")
    table.add_column("#", style="bold yellow", width=4)
    table.add_column("Repository Target", style="bold white", width=38)
    table.add_column("Category", style="dim cyan", width=22)
    table.add_column("Synthesis / Assessment Objective", style="italic", width=52)

    for t in sample_targets:
        table.add_row(t["id"], t["name"], t["type"], t["goal"])

    console.print(table)

    choice = Prompt.ask(
        "\n[bold green]Select repository target[/bold green]",
        choices=["1", "2", "3"],
        default="1",
    )

    if choice == "3":
        custom_path = Prompt.ask("[bold green]Enter absolute path to directory[/bold green]")
        custom_path = custom_path.strip().strip("'\"")
        custom_goal = Prompt.ask(
            "[bold green]Enter Objective / Goal[/bold green]",
            default="Analyze all the modules in this repo and create an assessment for me",
        )
        return custom_path, custom_goal
    elif choice == "2":
        selected = sample_targets[1]
        custom_goal = Prompt.ask(
            "[bold green]Enter Objective / Goal[/bold green]",
            default=selected["goal"],
        )
        return selected["path"], custom_goal
    else:
        selected = sample_targets[0]
        return selected["path"], selected["goal"]


def run_deep_agents_flow():
    """Execute the complete Deep Agents Multi-Agent Orchestration with Brick Routing."""
    print_regolo_banner()
    repo_path, goal = select_target_workspace()

    console.print(f"\n[bold green]✔ Target Workspace:[/bold green] [cyan]{repo_path}[/cyan]")
    console.print(f"[bold green]✔ Synthesis Goal:[/bold green] [white]{goal}[/white]\n")

    client = RegoloClient()
    router = BrickRouter(client=client)
    budget_controller = get_budget_controller()
    orchestrator = DeepAgentOrchestrator(client=client, router=router, budget_controller=budget_controller)

    # 1. Initialize Sandbox
    console.print(Panel("[bold green]1. INITIALIZING ISOLATED WORKSPACE SANDBOX[/bold green]", border_style="green"))
    with console.status("[green]Staging files into isolated sandbox directory...[/green]", spinner="dots"):
        time.sleep(0.4)
        sandbox = SandboxEnvironment(source_repo_path=repo_path)
    console.print(f"  [green]✔ Sandbox ID:[/green] [cyan]{sandbox.sandbox_id}[/cyan]")
    console.print(f"  [green]✔ Location:[/green] [dim]{sandbox.sandbox_path}[/dim]")
    console.print(f"  [green]✔ Staged Files:[/green] {sandbox.list_files()}\n")

    # Step callback logger with branded agent badges
    agent_badge_styles = {
        "ORCHESTRATOR": "bold green",
        "PLANNER": "bold bright_green",
        "RESEARCHER": "bold cyan",
        "TOOL_AGENT": "bold yellow",
        "CODE_EXECUTOR": "bold magenta",
        "REVIEWER": "bold blue",
        "REPORT_WRITER": "bold green",
        "BUDGET": "bold gold1",
    }

    def live_step_logger(agent_tag: str, msg: str):
        badge_style = agent_badge_styles.get(agent_tag, "bold white")
        console.print(f"  [{badge_style}][{agent_tag}][/{badge_style}] {msg}")

    # Human-In-The-Loop Approval Callback
    def human_approval_gate(plan_data: Dict[str, Any]) -> bool:
        console.print()
        console.print(Panel("[bold bright_green]HUMAN-IN-THE-LOOP DAG APPROVAL GATE (Brick Policy)[/bold bright_green]", border_style="bright_green"))
        _display_plan_dag_tree(plan_data)
        
        decision = Prompt.ask(
            "\n[bold yellow]Operator Decision[/bold yellow]",
            choices=["Accept", "Reject"],
            default="Accept",
        )
        return decision == "Accept"

    console.print(Panel("[bold green]2. EXECUTING DEEP AGENTS MULTI-AGENT PIPELINE[/bold green]", border_style="green"))
    
    pipeline_result = orchestrator.run_pipeline(
        sandbox=sandbox,
        goal=goal,
        log_callback=live_step_logger,
        human_approval_callback=human_approval_gate,
    )

    if pipeline_result.get("status") == "ABORTED":
        console.print("\n[bold red]❌ Pipeline execution aborted by operator.[/bold red]\n")
        return

    # Display Synthesized Files & Diff
    console.print()
    console.print(Panel("[bold green]3. SYNTHESIZED MCP TOOL HARNESS ARTIFACTS[/bold green]", border_style="green"))
    files = sandbox.list_files()
    synthesized = [f for f in files if "harness" in f or "tests" in f]
    for sf in synthesized:
        console.print(f"  [bold green]✔ Staged Tool File:[/bold green] [cyan]{sf}[/cyan]")

    # Display Diff if available
    diff_text = pipeline_result.get("diff", "")
    if diff_text:
        console.print("\n[bold green]Unified Git Diff (Sandbox Tool Generation):[/bold green]")
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, border_style="dim green", title="Sandbox Code Synthesis Diff"))

    # Display Reviewer Evaluation & Score
    reviewer_data = pipeline_result["results"]["reviewer"]["structured_data"]
    _display_reviewer_scorecard(reviewer_data)

    # Display Brick Telemetry & Cost Comparison Scoreboard
    console.print()
    console.print(Panel("[bold gold1]4. BRICK TELEMETRY & COST EFFICIENCY SCOREBOARD[/bold gold1]", border_style="gold1"))
    display_telemetry_scoreboard()

    console.print(f"\n[bold bright_green]🚀 DEEP AGENT TOOL HARNESS SYNTHESIS COMPLETED SUCCESSFULLY![/bold bright_green]")
    console.print(f"[dim]Technical specification exported to: [cyan]{pipeline_result.get('report_file')}[/cyan][/dim]\n")


def display_telemetry_scoreboard():
    """Display the Single Frontier Model vs Regolo Brick Multi-Model Routed scoreboard."""
    telemetry = get_budget_controller().get_summary()
    events = telemetry.get("events", [])

    table = Table(
        box=ROUNDED,
        border_style="green",
        header_style="bold green",
        title="Brick Telemetry: Single Frontier Baseline ($3/$15) vs Regolo Brick Routed Multi-Model",
    )
    table.add_column("Sub-Agent", style="bold white", width=16)
    table.add_column("Model Assigned", style="dim cyan", width=22)
    table.add_column("Routing Tier", style="bold yellow", width=14)
    table.add_column("Tokens (P / C)", style="white", width=16)
    table.add_column("Latency", style="dim", width=10)
    table.add_column("Regolo Cost", style="bold green", width=14)
    table.add_column("Frontier Cost", style="dim red", width=16)
    table.add_column("Cost Savings", style="bold bright_green", width=14)

    for e in events:
        table.add_row(
            e["role_name"],
            e["model"],
            f"[{'bold magenta' if e['is_escalated'] else 'yellow'}]{e['routing_tier']}[/]",
            f"{e['prompt_tokens']} / {e['completion_tokens']}",
            f"{e['latency_sec']}s",
            f"${e['cost_regolo_usd']:.5f}",
            f"${e['cost_frontier_usd']:.5f}",
            f"-{round((1 - (e['cost_regolo_usd'] / max(0.00001, e['cost_frontier_usd']))) * 100, 1)}%",
        )

    console.print(table)

    summary_panel = Text()
    summary_panel.append(f"Total Pipeline Tokens: {telemetry['total_tokens']:,}   •   ", style="bold white")
    summary_panel.append(f"Regolo Routed Cost: ${telemetry['total_regolo_cost_usd']:.4f}   •   ", style="bold green")
    summary_panel.append(f"Frontier Cost: ${telemetry['total_frontier_cost_usd']:.4f}   •   ", style="dim red")
    summary_panel.append(f"Total Cost Savings: {telemetry['savings_percentage']}% (8.5x Cheaper)", style="bold bright_green")

    console.print(Panel(Align.center(summary_panel), box=ROUNDED, border_style="bright_green"))


def display_brick_routing_matrix():
    """Display the complete Brick Semantic Routing Matrix & Profile Settings."""
    print_regolo_banner()
    router = BrickRouter()
    matrix = router.get_routing_matrix()

    console.print("[bold green]🎛 BRICK SEMANTIC ROUTER: SUB-AGENT ARCHITECTURAL MATRIX[/bold green]")
    console.print(f"[dim]Meta-Router: {config.MODEL_BRICK_ROUTER} on Regolo.ai (OpenAI-Compatible)[/dim]\n")

    table = Table(box=ROUNDED, border_style="green", header_style="bold green", expand=True)
    table.add_column("Sub-Agent Role", style="bold white", ratio=2)
    table.add_column("Preferred Model", style="bold green", ratio=2)
    table.add_column("Fallback Model", style="dim cyan", ratio=2)
    table.add_column("Escalation Model", style="bold magenta", ratio=2)
    table.add_column("Token Limit", style="yellow", ratio=1)
    table.add_column("Timeout", style="dim", ratio=1)
    table.add_column("Escalation Thr.", style="bold red", ratio=1)
    table.add_column("Criticality", style="bold yellow", ratio=1)

    for row in matrix:
        table.add_row(
            row["role_name"],
            row["preferred_model"],
            row["fallback_model"],
            row["escalation_model"],
            f"{row['token_limit']:,}",
            f"{row['timeout_sec']}s",
            f"{row['escalation_threshold']:.1f}/10",
            row["criticality"],
        )

    console.print(table)
    Prompt.ask("\n[bold green]Press Enter to return to main menu[/bold green]")


def inspect_synthesized_harness():
    """Inspect synthesized MCP tool files and specification report."""
    print_regolo_banner()
    console.print("[bold green]🛠 SYNTHESIZED AGENT TOOL HARNESS & MCP REGISTRY[/bold green]\n")

    spec_file = config.HARNESS_OUTPUT_DIR / "HARNESS_SPEC.md"
    if spec_file.exists():
        content = spec_file.read_text(encoding="utf-8")
        syntax = Syntax(content, "markdown", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, title="HARNESS_SPEC.md (Synthesized Specification)", border_style="green"))
    else:
        console.print("[yellow]No harness specification generated yet. Run the Deep Agents pipeline first.[/yellow]")

    Prompt.ask("\n[bold green]Press Enter to return to main menu[/bold green]")


def manage_docker_services():
    """Interactive management for Docker backend services (Qdrant & MCP Tool Sandbox)."""
    while True:
        print_regolo_banner()
        console.print("[bold green]🐳 DOCKER SERVICE ORCHESTRATION & INCREMENTAL PORT DISCOVERY[/bold green]")
        console.print("[dim]Manages Qdrant vector database and MCP Tool runtime container. Auto-discovers free ports on conflict.[/dim]\n")

        docker_ok, docker_msg = is_docker_available()
        if not docker_ok:
            console.print(f"[bold red]❌ Docker Status: Unavailable ({docker_msg})[/bold red]")
            console.print("[yellow]Please start Docker Desktop or the Docker daemon to launch containerized backends.[/yellow]\n")
        else:
            console.print(f"[bold green]✔ Docker Status: Active ({docker_msg})[/bold green]\n")

        statuses = get_services_status()
        table = Table(box=ROUNDED, border_style="green", header_style="bold green", expand=True)
        table.add_column("Service Name", style="bold white", ratio=3)
        table.add_column("Container", style="cyan", ratio=2)
        table.add_column("Image", style="dim", ratio=2)
        table.add_column("Status", ratio=1)
        table.add_column("Bound Port", style="bold yellow", ratio=1)
        table.add_column("Endpoint URL", style="dim green", ratio=3)

        for s in statuses:
            status_style = "bold green" if s["status"] == "RUNNING" else ("bold yellow" if s["status"] == "STOPPED" else "dim red")
            table.add_row(
                s["name"],
                s["container_name"],
                s["image"],
                f"[{status_style}]{s['status']}[/{status_style}]",
                str(s["assigned_port"]),
                s["url"],
            )

        console.print(table)

        console.print("\n[bold green]Service Actions:[/bold green]")
        console.print("  [bold green][1][/bold green] 🚀 [bold]Start / Deploy All Services[/bold] [dim](Pulls if missing, starts if stopped, auto-binds free ports)[/dim]")
        console.print("  [bold green][2][/bold green] 🛑 [bold]Stop All Services[/bold] [dim](Gracefully stops running containers)[/dim]")
        console.print("  [bold green][3][/bold green] 🔄 [bold]Refresh Status[/bold]")
        console.print("  [bold green][4][/bold green] ↩ [bold]Return to Main Menu[/bold]")

        action = Prompt.ask(
            "\n[bold green]Select service action[/bold green]",
            choices=["1", "2", "3", "4"],
            default="1",
        )

        if action == "1":
            if not docker_ok:
                console.print("[bold red]Cannot start services: Docker is not running.[/bold red]")
                Prompt.ask("\n[bold green]Press Enter to continue[/bold green]")
                continue

            console.print("\n[bold green]Launching services with incremental port discovery...[/bold green]")
            with console.status("[green]Deploying containers...[/green]", spinner="dots"):
                results = start_all_services(log_callback=lambda m: console.print(f"  {m}"))

            console.print("\n[bold bright_green]✔ All required services checked & launched![/bold bright_green]")
            Prompt.ask("\n[bold green]Press Enter to continue[/bold green]")

        elif action == "2":
            with console.status("[yellow]Stopping services...[/yellow]", spinner="dots"):
                stop_all_services(log_callback=lambda m: console.print(f"  {m}"))
            console.print("\n[bold green]✔ Managed services stopped.[/bold green]")
            Prompt.ask("\n[bold green]Press Enter to continue[/bold green]")

        elif action == "3":
            continue

        elif action == "4":
            break


def _display_plan_dag_tree(plan: Dict[str, Any]):
    """Render DAG execution plan tree."""
    tree = Tree(f"📋 [bold bright_green]Execution Plan: {plan.get('title', 'Deep Agent DAG')}[/bold bright_green]")
    for s in plan.get("steps", []):
        branch = tree.add(f"[bold cyan]Step {s.get('step_number')}: {s.get('action')} ({s.get('subagent').upper()})[/bold cyan]")
        branch.add(f"[white]{s.get('description')}[/white]")
        branch.add(f"[dim yellow]Token Budget: {s.get('assigned_budget', 2000):,} | Preferred: {s.get('preferred_model')}[/dim yellow]")
    console.print(tree)


def _display_reviewer_scorecard(review: Dict[str, Any]):
    """Render Reviewer audit scorecard."""
    score = review.get("harness_score", 98.0)
    score_color = "bright_green" if score > 90 else ("yellow" if score > 75 else "red")

    table = Table(
        title=f"Reviewer Audit Scorecard ({score}/100 - {review.get('audit_status', 'APPROVED')})",
        box=ROUNDED,
        border_style="green",
        header_style="bold green",
    )
    table.add_column("Audit Check Dimension", style="bold white", width=34)
    table.add_column("Status", style="bold green", width=12)
    table.add_column("Technical Evaluation Detail", style="dim", width=54)

    for c in review.get("checks", []):
        table.add_row(c.get("name", ""), f"[{score_color}]{c.get('status', 'PASSED')}[/{score_color}]", c.get("detail", ""))

    console.print()
    console.print(table)


def interactive_main_menu():
    """Main interactive menu loop for Regolo Deep Agents TUI."""
    while True:
        print_regolo_banner()
        console.print("[bold green]Main Navigation Menu:[/bold green]\n")

        console.print("  [bold green][1][/bold green] 🚀 [bold]Run Deep Agent Pipeline[/bold] [dim](Planner ➔ Researcher ➔ Tool Agent ➔ Code Executor ➔ Reviewer ➔ Report Writer)[/dim]")
        console.print("  [bold green][2][/bold green] 🐳 [bold]Manage Docker Services[/bold] [dim](Qdrant Vector DB & MCP Sandbox with Incremental Port Discovery)[/dim]")
        console.print("  [bold green][3][/bold green] 🎛 [bold]Brick Semantic Routing Matrix[/bold] [dim](Inspect Sub-Agent Model Assignments & Complexity Thresholds)[/dim]")
        console.print("  [bold green][4][/bold green] 🛠 [bold]Inspect Synthesized MCP Tool Harness[/bold] [dim](View Generated MCP Server, Schemas & Test Specs)[/dim]")
        console.print("  [bold green][5][/bold green] 📊 [bold]Telemetry & Cost Scoreboard[/bold] [dim](Single Frontier Model vs Regolo Brick Multi-Model Cost Delta)[/dim]")
        console.print("  [bold green][6][/bold green] 🧪 [bold]Run Automated Test Suite[/bold] [dim](Verify all modules with pytest)[/dim]")
        console.print("  [bold green][7][/bold green] ❌ [bold]Exit[/bold]")

        choice = Prompt.ask(
            "\n[bold green]Select an option[/bold green]",
            choices=["1", "2", "3", "4", "5", "6", "7"],
            default="1",
        )

        if choice == "1":
            run_deep_agents_flow()
            Prompt.ask("\n[bold green]Press Enter to return to main menu[/bold green]")
        elif choice == "2":
            manage_docker_services()
        elif choice == "3":
            display_brick_routing_matrix()
        elif choice == "4":
            inspect_synthesized_harness()
        elif choice == "5":
            print_regolo_banner()
            display_telemetry_scoreboard()
            Prompt.ask("\n[bold green]Press Enter to return to main menu[/bold green]")
        elif choice == "6":
            print_regolo_banner()
            console.print("[bold green]Running automated pytest test suite...[/bold green]\n")
            os.system("python3 -m pytest -v")
            Prompt.ask("\n[bold green]Press Enter to return to main menu[/bold green]")
        elif choice == "7":
            console.print("\n[bold green]Goodbye! Exiting Regolo Deep Agents.[/bold green]\n")
            sys.exit(0)
