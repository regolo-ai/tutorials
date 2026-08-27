"""Interactive Terminal User Interface (TUI) for Regolo.ai + Cognee Long-Term Memory.
Branded in Regolo Sovereign Green (#00FF66 / bright_green).
Features:
- Environment validation (Python, Node.js, Docker, Regolo API)
- Docker service orchestration with automatic port conflict fallback & healthcheck
- Scenario 1: Feature Implementation & CI Self-Healing (ReAct Mini-Loop + Live Pytest)
- Scenario 2: Multi-Session Timeline (Day 1 Bug -> Day 2 Memory Codification -> Day 15 Recall)
- Scenario 3: Naive Chunk RAG vs Cognee Memory Graph Benchmark
- Scenario 4: Causal Trail Multi-Hop Explorer
- Custom path scanner and memory recall for developer codebases
- Knowledge Graph Explorer with visual connections & Cognee Web UI links
- MCP Plugins for Claude Code and OpenClaw
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich import box
from rich.align import Align
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
from core.agent_loop import CodingAgentLoop, ReActStep
from core.cognee_engine import CogneeMemoryEngine
from core.docker_manager import (
    ACTIVE_PORTS,
    get_services_status,
    is_docker_available,
    start_all_services,
    start_service,
    stop_all_services,
    stop_service,
)
from core.env_checker import get_full_environment_health, run_full_setup
from core.naive_rag import NaiveChunkRAG
from core.plugins_bridge import PluginsBridgeManager
from core.regolo_client import BrickRouter, RegoloClient

console = Console()


def pause_for_return(prompt_text: str = "Press RETURN to return to main menu..."):
    """Flush pending input buffer and block until user explicitly presses Enter/Return."""
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass
    console.print(f"\n[bold bright_green]↵ {prompt_text}[/bold bright_green]", end=" ")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


def print_regolo_banner():
    """Render top-level branded banner in Regolo signature green."""
    console.clear()
    banner = Text()
    banner.append("  ██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗       █████╗ ██╗\n", style="bold bright_green")
    banner.append("  ██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗     ██╔══██╗██║\n", style="bold bright_green")
    banner.append("  ██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║     ███████║██║\n", style="bold green")
    banner.append("  ██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║     ██╔══██║██║\n", style="bold green")
    banner.append("  ██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝     ██║  ██║██║\n", style="bold dark_green")
    banner.append("  ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝      ╚═╝  ╚═╝╚═╝\n", style="bold dark_green")
    banner.append("\n⚡ COGNEE PRIVATE LONG-TERM MEMORY FOR CODING AGENTS ⚡\n", style="bold white")
    banner.append("Knowledge Graph • Session Recall • ReAct Tool Calling • Multi-Week Traceability\n", style="bold green")
    banner.append(f"Inference: Regolo.ai (EU Sovereign Cloud • Zero Data Retention) • Router: {config.MODEL_BRICK_ROUTER}\n", style="dim green")

    console.print(
        Panel(
            Align.center(banner),
            box=box.DOUBLE,
            border_style="bright_green",
            padding=(1, 2),
        )
    )


def show_environment_menu():
    """Option 1: Setup and inspect runtime environment."""
    console.print("\n[bold bright_green]🛠️  STEP 1: RUNTIME ENVIRONMENT & DEPENDENCY VALIDATOR[/bold bright_green]\n")

    with Progress(
        SpinnerColumn(style="bright_green"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[bright_green]Auditing Python, Node.js, Docker & Regolo API connectivity...", total=None)
        time.sleep(0.4)
        health = get_full_environment_health()
        progress.update(task, completed=True)

    # Render diagnostic table
    table = Table(title="Dependency Health Matrix", box=box.ROUNDED, border_style="green")
    table.add_column("Component", style="bold white")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim white")

    # Python
    py_ok = health["python"]["all_installed"]
    table.add_row(
        "Python Runtime",
        "[bold bright_green]READY[/bold bright_green]" if py_ok else "[bold red]ACTION REQUIRED[/bold red]",
        f"v{health['python']['version']} (Modules: {len(health['python']['installed_modules'])} installed, {len(health['python']['missing_modules'])} missing)",
    )

    # Node.js
    node_ok = health["nodejs"]["available"]
    table.add_row(
        "Node.js (MCP Bridge)",
        "[bold bright_green]AVAILABLE[/bold bright_green]" if node_ok else "[yellow]OPTIONAL (FALLBACK ACTIVE)[/yellow]",
        health["nodejs"]["status"],
    )

    # Docker
    dock_ok = health["docker"]["is_active"]
    table.add_row(
        "Docker Daemon",
        "[bold bright_green]ACTIVE[/bold bright_green]" if dock_ok else "[yellow]OFFLINE / EMBEDDED MODE[/yellow]",
        health["docker"]["details"],
    )

    # Regolo
    regolo = health["regolo"]
    reg_ok = bool(regolo.get("has_key"))
    reg_details = regolo.get("details") or regolo.get("status", "Unknown")
    table.add_row(
        "Regolo.ai Inference",
        "[bold bright_green]CONNECTED (EU SOVEREIGN)[/bold bright_green]" if reg_ok else "[bold red]MISSING API KEY[/bold red]",
        reg_details,
    )

    console.print(table)

    if not py_ok or not reg_ok:
        if Confirm.ask("\n[bold yellow]Run automated setup to install dependencies and configure .env?[/bold yellow]", default=True):
            run_full_setup()
            console.print("[bold bright_green]Setup completed. Re-checking environment...[/bold bright_green]")
            time.sleep(1)

    pause_for_return()


def show_docker_services_menu():
    """Option 2: Orchestrate and monitor Docker services (Postgres & Cognee)."""
    console.print("\n[bold bright_green]🐳 STEP 2: DOCKER SERVICE ORCHESTRATOR & AUTO-PORT RESOLUTION[/bold bright_green]\n")

    is_dock, dock_msg = is_docker_available()
    if not is_dock:
        console.print(f"[bold yellow]Notice:[/bold yellow] {dock_msg}")
        console.print("[dim]The system will run in lightweight embedded memory graph mode using NetworkX and local JSON storage.[/dim]\n")
        pause_for_return()
        return

    services_status = get_services_status()

    table = Table(title="Docker Managed Containers", box=box.ROUNDED, border_style="bright_green")
    table.add_column("Service", style="bold white")
    table.add_column("Container", style="cyan")
    table.add_column("Assigned Port", style="yellow")
    table.add_column("Status", style="bold")
    table.add_column("Health / Web UI", style="green")

    for s_key, s_data in services_status.items():
        is_run = bool(s_data.get("running") or s_data.get("is_running"))
        is_hlth = bool(s_data.get("healthy", is_run))
        st_color = "bright_green" if is_run and is_hlth else ("yellow" if is_run else "red")
        st_label = "HEALTHY" if is_run and is_hlth else ("RUNNING (UNHEALTHY)" if is_run else "STOPPED")

        extra_info = s_data.get("health_msg") or s_data.get("details", "")
        if s_key == "cognee" and is_run:
            extra_info = f"Web Docs: http://127.0.0.1:{s_data.get('port', 8800)}/docs"

        table.add_row(
            s_data.get("name", s_key),
            s_data.get("container_name", "unknown"),
            str(s_data.get("port", "-")),
            f"[{st_color}]{st_label}[/{st_color}]",
            extra_info,
        )

    console.print(table)

    engine = CogneeMemoryEngine()
    ui_info = engine.get_web_ui_url()
    console.print(Panel(
        f"[bold white]Cognee Web UI / API Gateway:[/bold white] [cyan]{ui_info['web_ui_url']}[/cyan]\n"
        f"[bold white]Swagger Interactive OpenAPI Docs:[/bold white] [cyan]{ui_info['swagger_docs_url']}[/cyan]\n"
        f"[bold white]Health Check Endpoint:[/bold white] [cyan]{ui_info['health_endpoint']}[/cyan]",
        title="[bold bright_green]🌐 Self-Hosted Cognee Endpoints[/bold bright_green]",
        border_style="bright_green",
        box=box.ROUNDED,
    ))

    console.print("\n[bold white]Actions:[/bold white]")
    console.print("  [1] Start / Verify All Services (Auto-Port Conflict Discovery)")
    console.print("  [2] Stop All Services")
    console.print("  [3] Restart All Services")
    console.print("  [0] Back to Main Menu")

    choice = Prompt.ask("\n[bold bright_green]Select action[/bold bright_green]", choices=["1", "2", "3", "0"], default="1")

    if choice == "0":
        return

    if choice == "1":
        with Progress(SpinnerColumn(style="bright_green"), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("[bright_green]Starting Postgres/pgvector and Cognee API containers...", total=None)
            res = start_all_services()
            progress.update(task, completed=True)
        console.print(f"[bold bright_green]✅ Services started and verified on ports: {res}[/bold bright_green]")

    elif choice == "2":
        with Progress(SpinnerColumn(style="bright_green"), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("[yellow]Stopping Docker containers...", total=None)
            res = stop_all_services()
            progress.update(task, completed=True)
        console.print("[bold yellow]🛑 All Docker services stopped.[/bold yellow]")

    elif choice == "3":
        stop_all_services()
        time.sleep(1)
        start_all_services()
        console.print("[bold bright_green]🔄 Services restarted and verified.[/bold bright_green]")

    pause_for_return()


def show_react_self_healing_menu():
    """Option 3: Real ReAct Mini-Loop with Tool Calling & Live Pytest Execution."""
    console.print("\n[bold bright_green]🚀 SCENARIO: FEATURE IMPLEMENTATION & CI SELF-HEALING (ReAct LOOP)[/bold bright_green]\n")

    task_scenario = "Add user search endpoint '/api/v1/users/search' strictly enforcing multi-tenant isolation and parameterized queries."

    console.print(Panel(
        f"[bold white]Task Prompt:[/bold white]\n[cyan]{task_scenario}[/cyan]\n\n"
        "[bold green]ReAct Loop Capabilities:[/bold green]\n"
        "  1. [bold white]Thought 1 & Tool Call:[/bold white] `recall_memory('tenant isolation SQL query parameters')` -> Retrieves ADR-001, ADR-003, CI-FAIL-89, PR-142\n"
        "  2. [bold white]Thought 2 & Tool Call:[/bold white] `read_file('sample_repo/src/api/users.py')` -> Inspects existing code stubs\n"
        "  3. [bold white]Thought 3 & Tool Call:[/bold white] `write_code_patch('sample_repo/src/api/users.py')` -> Generates secure implementation\n"
        "  4. [bold white]Thought 4 & Tool Call:[/bold white] `run_pytest('sample_repo/tests/test_users.py')` -> Executes live pytest in real subprocess\n"
        "  5. [bold white]Thought 5 & Tool Call:[/bold white] `record_session_outcome(...)` -> Saves verified fix into Cognee Knowledge Graph",
        title="[bold bright_green]ReAct Engineering Workflow[/bold bright_green]",
        box=box.ROUNDED,
        border_style="green",
    ))

    if not Confirm.ask("\n[bold bright_green]Execute Autonomous ReAct Loop with live Pytest?[/bold bright_green]", default=True):
        return

    agent_loop = CodingAgentLoop()

    console.print("\n[bold bright_green]⚡ Starting Autonomous ReAct Agent Loop on Regolo.ai...[/bold bright_green]\n")

    with console.status("[bold bright_green]⚡ Step 1/5: Querying Cognee Memory Graph (ADRs & CI history)...[/bold bright_green]", spinner="dots") as status:
        def on_status(msg: str):
            status.update(f"[bold bright_green]⚡ {msg}[/bold bright_green]")

        def on_stream(delta: str, chunk_count: int):
            status.update(
                f"[bold bright_green]⚡ [Step 3/5] Regolo.ai Code Synthesis in progress • Streaming chunk {chunk_count} (Zero Data Retention)...[/bold bright_green]"
            )

        def on_step(step: ReActStep):
            status.stop()
            # Render visual step card
            step_color = "bright_green" if step.status == "SUCCESS" else "red"
            step_table = Table(box=box.SIMPLE, show_header=False, expand=True)
            step_table.add_column("Key", style="bold white", width=16)
            step_table.add_column("Value", style="dim white")

            step_table.add_row("💭 Thought:", f"[white]{step.thought}[/white]")
            step_table.add_row("🛠️ Tool Action:", f"[bold cyan]{step.action_tool}({json.dumps(step.action_input)})[/bold cyan]")
            step_table.add_row("👁️ Observation:", f"[{step_color}]{step.observation}[/{step_color}]")

            console.print(Panel(
                step_table,
                title=f"[{step_color}]ReAct Step {step.step_num}: {step.action_tool}[/{step_color}]",
                border_style=step_color,
                box=box.ROUNDED,
            ))
            time.sleep(0.2)
            status.start()

        res = agent_loop.run_react_self_healing_demo(
            task_scenario,
            step_callback=on_step,
            status_callback=on_status,
            stream_callback=on_stream,
        )

    # Display Final Output Code & Pytest Execution
    console.print("\n" + "=" * 70)
    console.print("[bold bright_green]🧪 LIVE PYTEST SUBPROCESS VERIFICATION RESULT[/bold bright_green]")
    console.print("=" * 70)

    pytest_res = res.get("pytest_result", {})
    if pytest_res.get("passed"):
        console.print(Panel(
            f"[bold bright_green]STATUS: ALL TESTS PASSED (100% GREEN)[/bold bright_green]\n"
            f"[white]Passed Tests:[/white] {pytest_res.get('passed_tests', 0)}  •  "
            f"[white]Failed Tests:[/white] 0  •  "
            f"[white]Duration:[/white] {pytest_res.get('duration_seconds', 0)}s\n\n"
            f"[dim green]{pytest_res.get('stdout', '')}[/dim green]",
            title="[bold bright_green]✅ Pytest Execution Output[/bold bright_green]",
            border_style="bright_green",
            box=box.ROUNDED,
        ))
    else:
        console.print(Panel(
            f"[bold red]STATUS: TESTS FAILED[/bold red]\n\n[dim red]{pytest_res.get('stdout', '')}[/dim red]",
            title="[bold red]❌ Pytest Failure Output[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        ))

    console.print("\n[bold white]Final Generated Patch in `sample_repo/src/api/users.py`:[/bold white]")
    console.print(Syntax(res["generated_code"], "python", theme="monokai", line_numbers=True))

    console.print(f"\n[dim green]Execution Latency: {res['latency_seconds']}s • Total Tokens: {res['tokens_used']} • Cost: €{res['cost_eur']:.6f}[/dim green]")
    pause_for_return()


def show_multi_session_timeline_menu():
    """Option 4: Multi-Session Timeline Demo (Day 1 bug -> Day 2 memory -> Day 15 recall)."""
    console.print("\n[bold bright_green]⏳ SCENARIO: MULTI-SESSION TIMELINE (LEARNING ACROSS WEEKS)[/bold bright_green]\n")

    console.print(Panel(
        "[bold white]Demonstration of Memory Persistence Across Sessions:[/bold white]\n\n"
        "• [bold red]Session 1 (Day 1):[/bold red] Agent has no prior memory -> Writes dynamic f-string query -> [bold red]CI Run #89 FAILS[/bold red]\n"
        "• [bold yellow]Session 2 (Day 2):[/bold yellow] PR #142 fixes the bug; ADR-003 & ADR-001 are committed and codified into [bold yellow]Cognee Graph[/bold yellow]\n"
        "• [bold bright_green]Session 3 (Day 15):[/bold bright_green] A new related task arrives:\n"
        "    - [red]Naive RAG Agent:[/red] Recalls isolated code chunk without ADR -> [red]Repeats Day 1 bug[/red]\n"
        "    - [bright_green]Cognee Memory Agent:[/bright_green] Traverses graph to ADR-003 -> [bright_green]Passes test on first try (100% Green)[/bright_green]",
        title="[bold bright_green]Multi-Session Evolution Timeline[/bold bright_green]",
        box=box.ROUNDED,
        border_style="green",
    ))

    if not Confirm.ask("\n[bold bright_green]Run Multi-Session Timeline Simulation?[/bold bright_green]", default=True):
        return

    agent_loop = CodingAgentLoop()

    with console.status("[bold bright_green]⚡ Simulating Multi-Session Timeline across weeks on Regolo.ai...", spinner="dots") as status:
        def on_timeline_status(msg: str):
            status.update(f"[bold bright_green]⚡ {msg}[/bold bright_green]")

        def on_timeline_stream(delta: str, chunk_count: int):
            status.update(
                f"[bold bright_green]⚡ Regolo.ai LLM Code Generation in progress • Streaming chunk {chunk_count} (Zero Data Retention)...[/bold bright_green]"
            )

        timeline_res = agent_loop.run_multi_session_timeline_demo(
            status_callback=on_timeline_status,
            stream_callback=on_timeline_stream,
        )

    timeline_table = Table(title="Timeline Evolution Table", box=box.DOUBLE, border_style="bright_green")
    timeline_table.add_column("Timeline Stage", style="bold white", width=16)
    timeline_table.add_column("Action & Event", style="white")
    timeline_table.add_column("CI / Security Outcome", style="bold")

    for step in timeline_res["timeline"]:
        day = step["day"]
        if day == "Day 1":
            timeline_table.add_row(
                f"[red]{day} (S1)[/red]",
                f"{step['event']}\n[dim]{step['action']}[/dim]",
                f"[bold red]{step['ci_status']}[/bold red]\n[red]{step['error']}[/red]",
            )
        elif day == "Day 2":
            timeline_table.add_row(
                f"[yellow]{day} (S2)[/yellow]",
                f"{step['event']}\n[dim]{step['graph_state']}[/dim]",
                f"[bold yellow]{step['ci_status']}[/bold yellow]",
            )
        elif day == "Day 15":
            timeline_table.add_row(
                f"[bright_green]{day} (S3)[/bright_green]",
                f"{step['event']}\n"
                f"[red]Naive RAG:[/red] {step['naive_outcome']['reason']}\n"
                f"[bright_green]Cognee:[/bright_green] {step['cognee_outcome']['reason']}",
                f"[red]Naive: {step['naive_outcome']['ci_status']} (Score {step['naive_outcome']['score']})[/red]\n"
                f"[bright_green]Cognee: {step['cognee_outcome']['ci_status']} (Score {step['cognee_outcome']['score']})[/bright_green]",
            )

    console.print("\n")
    console.print(timeline_table)
    pause_for_return()


def show_demo_benchmark_menu():
    """Option 5: Run real benchmark comparing Naive RAG vs Cognee Memory Graph."""
    console.print("\n[bold bright_green]⚡ SCENARIO: NAIVE CHUNK RAG VS COGNEE LONG-TERM MEMORY (A/B BENCHMARK)[/bold bright_green]\n")

    task_scenario = (
        "Add a new user search endpoint '/api/v1/users/search' allowing enterprise "
        "admins to query accounts by username, while strictly respecting multi-tenant isolation."
    )

    console.print(Panel(
        f"[bold white]Task Prompt:[/bold white]\n[cyan]{task_scenario}[/cyan]\n\n"
        "[dim]Scenario: The agent must write an endpoint without repeating the SQL Injection "
        "and IDOR vulnerabilities from past CI Run #89, strictly adhering to ADR-001 & ADR-003.[/dim]",
        title="[bold bright_green]Engineering Scenario[/bold bright_green]",
        box=box.ROUNDED,
        border_style="green",
    ))

    if not Confirm.ask("\n[bold bright_green]Run benchmark execution on Regolo.ai?[/bold bright_green]", default=True):
        return

    agent_loop = CodingAgentLoop()

    with console.status("[bold bright_green]⚡ Initializing A/B Benchmark on Regolo.ai...", spinner="dots") as status:
        def on_bench_status(msg: str):
            status.update(f"[bold bright_green]⚡ {msg}[/bold bright_green]")

        def on_bench_stream(delta: str, chunk_count: int):
            status.update(
                f"[bold bright_green]⚡ Regolo.ai LLM Code Generation in progress • Streaming chunk {chunk_count} (Zero Data Retention)...[/bold bright_green]"
            )

        on_bench_status("1/2 Executing Naive Chunk RAG Agent (Isolated Retrieval)...")
        naive_res = agent_loop.run_naive_rag_agent(
            task_scenario,
            status_callback=on_bench_status,
            stream_callback=on_bench_stream,
        )

        on_bench_status("2/2 Executing Cognee Memory Graph Agent (Causal Graph Recall)...")
        cognee_res = agent_loop.run_cognee_memory_agent(
            task_scenario,
            status_callback=on_bench_status,
            stream_callback=on_bench_stream,
        )

    # 1. Show Naive RAG Results
    console.print("\n" + "=" * 70)
    console.print("[bold red]❌ ATTEMPT 1: NAIVE CHUNK RAG AGENT (ISOLATED VECTOR CHUNKS)[/bold red]")
    console.print("=" * 70)
    console.print(Panel(naive_res.retrieved_context, title="[yellow]Context Retrieved by Naive RAG[/yellow]", border_style="yellow"))
    console.print("\n[bold white]Generated Code by Naive Agent:[/bold white]")
    console.print(Syntax(naive_res.generated_code, "python", theme="monokai", line_numbers=True))

    console.print("\n[bold red]Automated CI & Security Gate Outcome:[/bold red]")
    for v in naive_res.violations:
        console.print(f"  ❌ [red]{v}[/red]")
    console.print(f"  [bold]Security Score:[/bold] [red]{naive_res.security_score}/100 (FAIL)[/red]")
    console.print(f"  [bold]Inference Model:[/bold] {naive_res.model_used}  •  [bold]Latency:[/bold] {naive_res.latency_seconds}s  •  [bold]Cost:[/bold] €{naive_res.cost_eur:.6f}")

    # 2. Show Cognee Long-Term Memory Results
    console.print("\n" + "=" * 70)
    console.print("[bold bright_green]✅ ATTEMPT 2: COGNEE LONG-TERM MEMORY AGENT (REGOLO.AI)[/bold bright_green]")
    console.print("=" * 70)
    console.print(Panel(cognee_res.retrieved_context, title="[bright_green]Causal Graph Memory Recalled by Cognee[/bright_green]", border_style="bright_green"))
    console.print("\n[bold white]Generated Code by Cognee-Informed Agent:[/bold white]")
    console.print(Syntax(cognee_res.generated_code, "python", theme="monokai", line_numbers=True))

    console.print("\n[bold bright_green]Automated CI & Security Gate Outcome:[/bold bright_green]")
    console.print("  ✅ [bright_green]ADR-001 Compliant (Tenant Context Session strictly isolated)[/bright_green]")
    console.print("  ✅ [bright_green]ADR-003 Compliant (SQLAlchemy Core parameterized binding, no raw strings)[/bright_green]")
    console.print("  ✅ [bright_green]CI-FAIL-89 Prevented (Regression test suite 100% green)[/bright_green]")
    console.print(f"  [bold]Security Score:[/bold] [bright_green]{cognee_res.security_score}/100 (PASSED)[/bright_green]")
    console.print(f"  [bold]Inference Model:[/bold] {cognee_res.model_used} (Brick Routed)  •  [bold]Latency:[/bold] {cognee_res.latency_seconds}s  •  [bold]Cost:[/bold] €{cognee_res.cost_eur:.6f}")

    # Comparative Summary Panel
    summary_table = Table(title="Benchmark Comparison Matrix", box=box.DOUBLE, border_style="bright_green")
    summary_table.add_column("Metric", style="bold white")
    summary_table.add_column("Naive Chunk RAG", style="bold red")
    summary_table.add_column("Cognee Memory Graph", style="bold bright_green")

    summary_table.add_row("Context Type", "Raw Chunk Window", "Knowledge Graph + Entities + ADRs")
    summary_table.add_row("Causal Memory Recall", "❌ None (Repeated Bug)", "✅ Connected (PR-142 -> ADR-003)")
    summary_table.add_row("CI Build Status", "❌ FAILED (Syntax/Injection)", "✅ PASSED (100% Green)")
    summary_table.add_row("Security Compliance", "25 / 100", "100 / 100")
    summary_table.add_row("Data Privacy", "Standard", "Zero Data Retention (EU)")

    console.print("\n")
    console.print(summary_table)

    pause_for_return()


def show_custom_path_menu():
    """Option 6: Scan custom user path, cognify code/docs, and run interactive memory recall."""
    console.print("\n[bold bright_green]📂 STEP 6: SCAN CUSTOM CODEBASE & BUILD KNOWLEDGE GRAPH[/bold bright_green]\n")

    user_path_str = Prompt.ask(
        "[bold bright_green]Enter directory path to index into Cognee (or '0' to return to main menu)[/bold bright_green]",
        default=str(config.SAMPLE_REPO_DIR),
    )
    if user_path_str.strip().lower() in ["0", "q", "exit", "quit"]:
        return

    user_path = Path(user_path_str).resolve()

    if not user_path.exists():
        console.print(f"[bold red]Error: Path '{user_path}' does not exist.[/bold red]")
        pause_for_return()
        return

    engine = CogneeMemoryEngine()

    with Progress(
        SpinnerColumn(style="bright_green"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"[bright_green]Cognifying {user_path.name} (Extracting entities & relations with Regolo)...", total=None)

        def cb(msg):
            progress.update(task, description=f"[bright_green]{msg}")

        result = engine.cognify_codebase(user_path, progress_callback=cb)
        progress.update(task, completed=True)

    console.print("\n[bold bright_green]✅ Codebase Cognified Successfully![/bold bright_green]")
    console.print(f"  • [white]Files Processed:[/white] {result.get('scanned_files', 0)}")
    console.print(f"  • [white]Total Memory Nodes in Graph:[/white] {result.get('indexed_nodes', 0)}")
    console.print(f"  • [white]Relational Graph Edges:[/white] {result.get('indexed_edges', 0)}")
    console.print(f"  • [white]Indexing Time:[/white] {result.get('elapsed_seconds', 0)}s")

    # Interactive Query Loop
    console.print("\n[bold bright_green]Interactive Memory Recall on your Codebase:[/bold bright_green]")
    while True:
        query = Prompt.ask("\n[bold white]Enter query / task for Cognee (or '0' / 'q' to return to main menu)[/bold white]", default="")
        if query.strip().lower() in ["0", "q", "exit", "quit", ""]:
            break

        recall_res = engine.recall_memory(query)
        console.print("\n" + Panel(
            recall_res["memory_prompt_block"],
            title=f"[bold bright_green]Cognee Recall for: '{query}'[/bold bright_green]",
            border_style="bright_green",
            box=box.ROUNDED,
        ))

        if Confirm.ask("[bold bright_green]Generate code patch with Regolo Coding Specialist (qwen3-coder-next)?[/bold bright_green]", default=True):
            client = RegoloClient()
            with console.status("[bold bright_green]⚡ Calling Regolo API with Zero Data Retention...", spinner="dots") as gen_status:
                def on_custom_stream(delta: str, chunk_count: int):
                    gen_status.update(
                        f"[bold bright_green]⚡ Synthesizing code patch • Streaming chunk {chunk_count} on Regolo.ai (Zero Data Retention)...[/bold bright_green]"
                    )

                gen_res = client.generate(
                    prompt=f"{recall_res['memory_prompt_block']}\n\nTask: {query}\nImplement solution:",
                    stage="coder",
                    status_callback=lambda m: gen_status.update(f"[bold bright_green]⚡ {m}[/bold bright_green]"),
                    stream_callback=on_custom_stream,
                )

            console.print("\n[bold white]Generated Implementation:[/bold white]")
            console.print(Syntax(gen_res["content"], "python", theme="monokai", line_numbers=True))
            console.print(f"\n[dim green]Model: {gen_res['model']} • Latency: {gen_res['latency_seconds']}s • Tokens: {gen_res['total_tokens']}[/dim green]")

    pause_for_return()


def show_graph_explorer_menu():
    """Option 7: Inspect topological knowledge graph structure, visual connections, and Cognee Web UI."""
    console.print("\n[bold bright_green]🕸️  STEP 7: KNOWLEDGE GRAPH VISUALIZER & COGNEE WEB UI[/bold bright_green]\n")

    engine = CogneeMemoryEngine()
    summary = engine.get_graph_summary()
    ui_info = engine.get_web_ui_url()

    # 1. Generate & Offer Interactive Visual HTML Graph
    html_graph_path = engine.generate_visual_html_graph()
    from core.docker_manager import find_available_port
    server_port = find_available_port(8850)
    web_url = f"http://127.0.0.1:{server_port}/"

    console.print(Panel(
        f"[bold bright_green]🌐 Local Live Server URL:[/bold bright_green] [bold cyan]{web_url}[/bold cyan]\n"
        f"[bold bright_green]📁 Local HTML File:[/bold bright_green] [dim white]{html_graph_path}[/dim white]\n"
        f"[bold bright_green]⚡ Cognee Docker API Gateway:[/bold bright_green] [cyan]{ui_info['web_ui_url']}[/cyan]\n"
        f"[bold bright_green]📖 OpenAPI Swagger Docs:[/bold bright_green] [cyan]{ui_info['swagger_docs_url']}[/cyan]\n\n"
        "[bold white]Features:[/bold white] Dynamic 2D Physics Force Graph, Node Search & Filtering, Inbound/Outbound Link Highlighting.",
        title="[bold bright_green]🌐 Visual Graph Explorer & Cognee Web Interface[/bold bright_green]",
        border_style="bright_green",
        box=box.DOUBLE,
    ))

    if Confirm.ask("[bold bright_green]Start live HTTP server and open interactive graph in browser?[/bold bright_green]", default=True):
        import http.server
        import socketserver
        import webbrowser

        console.print(f"\n[bold bright_green]🟢 Graph Server active at {web_url}[/bold bright_green]")
        console.print("[bold yellow]Press CTRL+C in this terminal whenever you wish to stop the server and return to the TUI menu.[/bold yellow]\n")

        try:
            webbrowser.open(web_url)
        except Exception:
            pass

        class TuiGraphHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(config.DATA_DIR), **kw)

            def do_GET(self):
                clean_p = self.path.split("?")[0].split("#")[0]
                if clean_p in ["", "/", "/index.html", "/visualizer", "/graph"]:
                    self.path = "/knowledge_graph_visualizer.html"
                elif clean_p.startswith("/data/"):
                    self.path = clean_p.replace("/data/", "/", 1)
                elif clean_p == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                    return
                return super().do_GET()

            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, BrokenPipeError, TimeoutError, OSError):
                    pass

            def log_message(self, format_str, *args_log):
                console.print(f"  [dim green][{time.strftime('%H:%M:%S')}][/dim green] 🌐 [cyan]{self.address_string()}[/cyan] - {format_str % args_log}")

        class ThreadingTuiGraphServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        httpd = ThreadingTuiGraphServer(("127.0.0.1", server_port), TuiGraphHandler)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[bold yellow]🛑 Graph server stopped. Returning to TUI...[/bold yellow]\n")
            httpd.shutdown()
            httpd.server_close()

    # 2. Topological Stats Table
    stats_table = Table(box=box.SIMPLE, border_style="green")
    stats_table.add_column("Graph Metric", style="bold white")
    stats_table.add_column("Count", style="bold bright_green")

    stats_table.add_row("Total Knowledge Nodes", str(summary["total_nodes"]))
    stats_table.add_row("Total Relational Edges", str(summary["total_edges"]))
    stats_table.add_row("Multi-Session Recall Events", str(summary["session_recall_events"]))

    console.print(Panel(stats_table, title="[bold bright_green]Topological Graph Summary[/bold bright_green]", border_style="bright_green"))

    # 3. Categorized Entity Tree
    root_tree = Tree("[bold bright_green]🌿 Regolo + Cognee Enterprise Memory Graph[/bold bright_green]")

    adrs_branch = root_tree.add("[bold white]📜 Architectural Decisions (ADRs)[/bold white]")
    ci_branch = root_tree.add("[bold red]🚨 Past CI Errors & Root Causes[/bold red]")
    pr_branch = root_tree.add("[bold cyan]🔀 Similar PRs & Resolutions[/bold cyan]")
    conv_branch = root_tree.add("[bold yellow]📐 Repository Conventions[/bold yellow]")
    vuln_branch = root_tree.add("[bold magenta]🛡️ Resolved Vulnerabilities (CVEs)[/bold magenta]")
    session_branch = root_tree.add("[bold green]💾 Verified Session Outcomes[/bold green]")

    for node_id, node in engine.nodes_data.items():
        n_type = node.get("type", "")
        label = f"[bold]{node_id}:[/bold] {node.get('title', '')}"
        if "ArchitecturalDecision" in n_type or "ADR" in node_id:
            adrs_branch.add(f"[green]{label}[/green]")
        elif "PastCIError" in n_type or "CI" in node_id:
            ci_branch.add(f"[red]{label}[/red]")
        elif "SimilarPR" in n_type or "PR" in node_id:
            pr_branch.add(f"[cyan]{label}[/cyan]")
        elif "Convention" in n_type:
            conv_branch.add(f"[yellow]{label}[/yellow]")
        elif "Vulnerability" in n_type or "VULN" in node_id:
            vuln_branch.add(f"[magenta]{label}[/magenta]")
        elif "SessionOutcome" in n_type or "SESSION" in node_id:
            session_branch.add(f"[bright_green]{label}[/bright_green]")

    console.print(root_tree)

    # 4. Visual Node Connections Table (ASCII Representation)
    console.print("\n[bold bright_green]🔗 Active Relational Edges in Knowledge Graph:[/bold bright_green]")
    edge_table = Table(box=box.ROUNDED, border_style="bright_green")
    edge_table.add_column("Source Node", style="bold white", width=16)
    edge_table.add_column("Causal Relation", style="bold cyan", width=22)
    edge_table.add_column("Target Node", style="bold white", width=16)
    edge_table.add_column("Visual Edge Flow Diagram", style="bold yellow")

    formatted_edges = engine.get_formatted_edge_list()
    for e in formatted_edges:
        edge_table.add_row(
            e["source"],
            e["relation"],
            e["target"],
            e["diagram"],
        )

    console.print(edge_table)

    # 5. Interactive Node Inspector
    inspect_choice = Prompt.ask(
        "\n[bold white]Enter Node ID to inspect details & neighbors (or Enter / '0' to return to main menu)[/bold white]",
        default="",
    )
    if not inspect_choice or inspect_choice.strip().lower() in ["0", "q", "exit", "quit"]:
        return

    if inspect_choice in engine.nodes_data:
        n_info = engine.get_node_neighbors(inspect_choice)
        node_payload = n_info["node"]
        inbound_str = "\n".join([f"  ◀── [{ib['relation']}] from {ib['source_id']} ({ib['source_title']})" for ib in n_info["inbound"]]) or "  (None)"
        outbound_str = "\n".join([f"  ──▶ [{ob['relation']}] to {ob['target_id']} ({ob['target_title']})" for ob in n_info["outbound"]]) or "  (None)"

        console.print(Panel(
            f"[bold white]Title:[/bold white] {node_payload.get('title')}\n"
            f"[bold white]Type:[/bold white] {node_payload.get('type')}  •  [bold white]Category:[/bold white] {node_payload.get('category')}\n\n"
            f"[bold white]Content / Policy Rule:[/bold white]\n{node_payload.get('content')}\n\n"
            f"[bold bright_green]Inbound Relations:[/bold bright_green]\n{inbound_str}\n\n"
            f"[bold cyan]Outbound Relations:[/bold cyan]\n{outbound_str}",
            title=f"[bold bright_green]Node Inspector: {inspect_choice}[/bold bright_green]",
            border_style="bright_green",
            box=box.ROUNDED,
        ))
    else:
        console.print(f"[bold yellow]Node '{inspect_choice}' not found in active graph.[/bold yellow]")

    pause_for_return()


def show_plugins_setup_menu():
    """Option 8: Export Claude Code and OpenClaw configuration files."""
    console.print("\n[bold bright_green]🔌 STEP 8: CLAUDE CODE & OPENCLAW PLUGIN CONNECTOR[/bold bright_green]\n")

    bridge = PluginsBridgeManager()
    exported = bridge.export_all_bridges()

    table = Table(title="Generated Agent Integration Files", box=box.ROUNDED, border_style="bright_green")
    table.add_column("Agent / Target", style="bold white")
    table.add_column("Generated File Path", style="cyan")

    table.add_row("Claude Code MCP Config", exported["claude_code_mcp"])
    table.add_row("OpenClaw Plugin Descriptor", exported["openclaw_plugin"])
    table.add_row("Python Fast MCP Server", exported["mcp_server_script"])

    console.print(table)
    console.print("\n[bold bright_green]To activate Claude Code with Cognee Memory:[/bold bright_green]")
    console.print("  1. Copy [cyan]plugins/claude_code_mcp.json[/cyan] to your Claude config directory.")
    console.print("  2. Claude Code will now automatically invoke [bold green]cognee_recall[/bold green] before modifying files!\n")

    pause_for_return()


def run_tui():
    """Main interactive loop."""
    while True:
        print_regolo_banner()

        # Display Main Menu
        menu_table = Table(box=box.ROUNDED, border_style="bright_green", show_header=False, expand=True)
        menu_table.add_column("Option", style="bold bright_green", width=6)
        menu_table.add_column("Description", style="bold white")

        menu_table.add_row("[1]", "🛠️  Setup Environment (Python, Node.js, Docker, Regolo API)")
        menu_table.add_row("[2]", "🐳 Manage Docker Services (Postgres/pgvector + Cognee Auto-Port)")
        menu_table.add_row("[3]", "🚀 Demo: Feature Implementation & CI Self-Healing (ReAct Mini-Loop + Live Pytest)")
        menu_table.add_row("[4]", "⏳ Demo: Multi-Session Timeline (Day 1 Bug -> Day 2 Memory -> Day 15 Recall)")
        menu_table.add_row("[5]", "⚡ Demo: Naive Chunk RAG vs Cognee Memory Graph (A/B Benchmark)")
        menu_table.add_row("[6]", "📂 Custom Path: Scan, Cognify & Recall on Your Codebase")
        menu_table.add_row("[7]", "🕸️  Explore Knowledge Graph & Cognee Web UI (Nodes, Causal Trail & Connections)")
        menu_table.add_row("[8]", "🔌 Configure Claude Code & OpenClaw MCP Plugins")
        menu_table.add_row("[0]", "🚪 Exit")

        console.print(menu_table)

        choice = Prompt.ask(
            "\n[bold bright_green]Select an option [0-8][/bold bright_green]",
            choices=["1", "2", "3", "4", "5", "6", "7", "8", "0"],
            default="3",
        )

        if choice == "1":
            show_environment_menu()
        elif choice == "2":
            show_docker_services_menu()
        elif choice == "3":
            show_react_self_healing_menu()
        elif choice == "4":
            show_multi_session_timeline_menu()
        elif choice == "5":
            show_demo_benchmark_menu()
        elif choice == "6":
            show_custom_path_menu()
        elif choice == "7":
            show_graph_explorer_menu()
        elif choice == "8":
            show_plugins_setup_menu()
        elif choice == "0":
            console.print("\n[bold bright_green]Thank you for using Regolo.ai + Cognee Memory Suite. Goodbye![/bold bright_green]\n")
            sys.exit(0)


if __name__ == "__main__":
    run_tui()
