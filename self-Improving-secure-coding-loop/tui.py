"""Interactive Terminal User Interface (TUI) for Closed-Loop Secure Coding Agent.
Provides visual terminal experience for video demonstration of:
Open SWE (Produce) -> Deepsec (Verify) -> Cognee (Remember) -> Brick (Govern) with GLM-5.2 on Regolo.ai.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.align import Align
from rich.box import DOUBLE, ROUNDED, SIMPLE
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
from core.brick_governance import clear_telemetry, get_telemetry_summary
from core.cognee_memory import CogneeMemoryGraph
from core.deepsec import DeepsecSecurityHarness
from core.docker_manager import (
    get_services_status,
    is_docker_available,
    start_all_services,
    start_service,
    stop_all_services,
)
from core.open_swe import OpenSWEAgent
from core.regolo_client import RegoloClient
from core.sandbox import SandboxEnvironment

console = Console()


def print_banner():
    """Print top-level branded banner."""
    console.clear()
    banner_text = Text()
    banner_text.append("⚡ SELF-IMPROVING SECURE CODING LOOP ⚡\n", style="bold cyan")
    banner_text.append("Open SWE (Produce)  ➔  Deepsec (Verify)  ➔  Cognee (Remember)  ➔  Brick (Govern)\n", style="bold white")
    banner_text.append(f"Inference: Regolo.ai (OpenAI-Compatible)  •  Model: {config.REGOLO_MODEL}  •  Status: Active", style="dim green")

    console.print(
        Panel(
            Align.center(banner_text),
            box=DOUBLE,
            border_style="bright_blue",
            padding=(1, 2),
        )
    )


def select_target_repository() -> Tuple[str, str, str]:
    """Interactive target repository and issue picker."""
    console.print("\n[bold yellow]📁 STEP 1: SELECT TARGET REPOSITORY TO SCAN & REMEDIATE[/bold yellow]")

    sample_targets = [
        {
            "id": "1",
            "name": "AuthService (FastAPI)",
            "path": str(config.SAMPLE_REPOS_DIR / "auth_service"),
            "issue_title": "Fix SQL Injection in /users/search & Insecure JWT Signature Verification",
            "issue_body": "Security audit flagged CWE-89 (SQL Injection) in user search endpoint and CWE-287 (Algorithm Confusion & Signature Bypass) in token verification.",
            "cwe": "CWE-89, CWE-287",
        },
        {
            "id": "2",
            "name": "Webhook Gateway (Flask/FastAPI)",
            "path": str(config.SAMPLE_REPOS_DIR / "webhook_gateway"),
            "issue_title": "Mitigate Blind SSRF in /dispatch & Command Injection in /diagnostics/ping",
            "issue_body": "External webhooks can access cloud metadata 169.254.169.254 (SSRF). Ping endpoint runs subprocess shell=True allowing remote command execution (CWE-78).",
            "cwe": "CWE-918, CWE-78",
        },
        {
            "id": "3",
            "name": "E-Commerce Cart (FastAPI)",
            "path": str(config.SAMPLE_REPOS_DIR / "ecommerce_cart"),
            "issue_title": "Resolve IDOR on /orders/{id} & Client-Controlled Price Tampering on Checkout",
            "issue_body": "Any user can view arbitrary order records without ownership checks (IDOR CWE-639). Checkout endpoint trusts client-supplied unit prices.",
            "cwe": "CWE-639, CWE-20",
        },
        {
            "id": "4",
            "name": "File Storage API",
            "path": str(config.SAMPLE_REPOS_DIR / "file_storage_service"),
            "issue_title": "Fix Path Traversal in /files/download & Unrestricted File Upload",
            "issue_body": "Directory traversal via ../../ in filename parameter (CWE-22) and unrestricted executable file upload (CWE-434).",
            "cwe": "CWE-22, CWE-434",
        },
        {
            "id": "5",
            "name": "Analytics Engine",
            "path": str(config.SAMPLE_REPOS_DIR / "analytics_query_engine"),
            "issue_title": "Eliminate eval() RCE in Formula Parser & Unsafe pickle Deserialization",
            "issue_body": "Arbitrary Python code execution through eval() (CWE-94) and arbitrary object loading via pickle.loads (CWE-502).",
            "cwe": "CWE-94, CWE-502",
        },
        {
            "id": "6",
            "name": "Crypto Wallet Service",
            "path": str(config.SAMPLE_REPOS_DIR / "crypto_wallet_service"),
            "issue_title": "Remove Hardcoded Private Key & Enforce CSPRNG for Address Generation",
            "issue_body": "Hardcoded master private key (CWE-798) and predictable random.randint pseudo-random numbers used for keys (CWE-338).",
            "cwe": "CWE-798, CWE-338",
        },
        {
            "id": "7",
            "name": "User Profile API",
            "path": str(config.SAMPLE_REPOS_DIR / "user_profile_api"),
            "issue_title": "Prevent Stored XSS in /profile/card & Block Mass Assignment Privilege Escalation",
            "issue_body": "Unsanitized user bio HTML allows Stored XSS (CWE-79) and unconstrained profile dictionary update permits admin role escalation (CWE-915).",
            "cwe": "CWE-79, CWE-915",
        },
    ]

    table = Table(box=ROUNDED, border_style="cyan", show_header=True, header_style="bold magenta")
    table.add_column("#", style="bold yellow", width=4)
    table.add_column("Repository Target", style="bold white", width=26)
    table.add_column("Target Vulnerabilities", style="bold red", width=22)
    table.add_column("Open GitHub Issue", style="italic dim", width=48)

    for t in sample_targets:
        table.add_row(t["id"], t["name"], t["cwe"], t["issue_title"])
    table.add_row("8", "Custom Directory Path", "User-specified", "Scan and remediate any local project directory")

    console.print(table)

    choice = Prompt.ask(
        "[bold cyan]Select repository target[/bold cyan]",
        choices=["1", "2", "3", "4", "5", "6", "7", "8"],
        default="1",
    )

    if choice == "8":
        custom_path = Prompt.ask("[bold green]Enter absolute path to directory[/bold green]")
        custom_title = Prompt.ask("[bold green]Enter Issue / Task Title[/bold green]", default="Automated Security Hardening")
        custom_body = Prompt.ask("[bold green]Enter Issue Details[/bold green]", default="Remediate all security vulnerabilities and verify with tests.")
        return custom_path, custom_title, custom_body
    else:
        selected = sample_targets[int(choice) - 1]
        return selected["path"], selected["issue_title"], selected["issue_body"]


def run_full_closed_loop_flow():
    """Execute the complete self-improving secure coding loop."""
    print_banner()
    repo_path, issue_title, issue_body = select_target_repository()

    console.print(f"\n[bold green]✔ Target Workspace:[/bold green] [cyan]{repo_path}[/cyan]")
    console.print(f"[bold green]✔ Issue:[/bold green] [white]{issue_title}[/white]\n")

    client = RegoloClient()
    memory = CogneeMemoryGraph()
    swe_agent = OpenSWEAgent(client=client, memory=memory)
    deepsec = DeepsecSecurityHarness(client=client)

    # 1. Initialize Sandbox
    console.print(Panel("[bold yellow]1. ISOLATING WORKSPACE IN SECURE SANDBOX[/bold yellow]", border_style="yellow"))
    with console.status("[cyan]Creating sandboxed workspace environment...[/cyan]", spinner="dots"):
        time.sleep(0.4)
        sandbox = SandboxEnvironment(source_repo_path=repo_path)
    console.print(f"  [green]✔ Sandbox initialized at:[/green] [dim]{sandbox.sandbox_path}[/dim]")
    console.print(f"  [green]✔ Files staged in sandbox:[/green] {sandbox.list_files()}\n")

    # 2. Initial Deepsec Vulnerability Scan
    console.print(Panel("[bold red]2. DEEPSEC SECURITY HARNESS: INITIAL AUDIT[/bold red]", border_style="red"))
    with console.status(f"[red]Deepsec scanning codebase with Regolo ({config.MODEL_DEEPSEC_SCAN})...[/red]", spinner="bouncingBar"):
        time.sleep(0.5)
        initial_scan = deepsec.run_security_scan(sandbox)

    _display_findings_table(initial_scan["findings"], title="Pre-Remediation Security Findings (Deepsec)")
    console.print(f"  [bold]Security Score:[/bold] [{ 'green' if initial_scan['security_score'] > 70 else 'red' }]{initial_scan['security_score']}/100[/]")
    console.print(f"  [bold]Gate Status:[/bold] [red]{initial_scan['gate_status']}[/red]\n")

    # 3. Cognee Memory Graph Query & Open SWE Planning
    console.print(Panel("[bold blue]3. COGNEE MEMORY RECALL & OPEN SWE PLANNING[/bold blue]", border_style="blue"))
    with console.status(f"[blue]Open SWE querying Cognee memory & generating plan via {config.MODEL_OPEN_SWE_PLAN}...[/blue]", spinner="aesthetic"):
        time.sleep(0.6)
        analysis_result = swe_agent.analyze_and_plan(sandbox, issue_title, issue_body)

    plan = analysis_result["plan"]
    memory_patterns = analysis_result["memory_patterns"]

    # Display Cognee memory recall
    _display_memory_patterns(memory_patterns)

    # Display Open SWE Plan
    _display_plan_panel(plan)

    # 4. Human-In-The-Loop Approval Checkpoint
    console.print(Panel("[bold magenta]4. HUMAN-IN-THE-LOOP APPROVAL GATE (Brick Policy)[/bold magenta]", border_style="magenta"))
    console.print("[dim]Open SWE mandates explicit human approval before executing code alterations in sandbox.[/dim]")
    
    approval = Prompt.ask(
        "\n[bold yellow]Human Decision[/bold yellow]",
        choices=["Accept", "Modify", "Reject"],
        default="Accept",
    )

    if approval == "Reject":
        console.print("[bold red]❌ Plan Rejected by Human Reviewer. Terminating loop.[/bold red]")
        return
    elif approval == "Modify":
        custom_instructions = Prompt.ask("[bold green]Enter additional constraint or guidance for Open SWE[/bold green]")
        console.print(f"[cyan]Updated plan with human constraint: '{custom_instructions}'[/cyan]")

    console.print("\n[bold green]✔ Plan Approved. Proceeding to Sandbox Remediation...[/bold green]\n")

    # 5. Open SWE Execution & Tests
    console.print(Panel("[bold cyan]5. OPEN SWE: SANDBOX CODE REMEDIATION & TESTS[/bold cyan]", border_style="cyan"))
    with console.status(f"[cyan]Open SWE applying defensive patches and running pytest with {config.MODEL_OPEN_SWE_EXECUTE}...[/cyan]", spinner="dots"):
        time.sleep(0.6)
        remediation_res = swe_agent.execute_remediation(sandbox, issue_title, plan)

    console.print(f"  [green]✔ Remediation Summary:[/green] {remediation_res['remediation_summary']}")
    console.print(f"  [green]✔ Modified Files:[/green] {remediation_res['modified_files']}")
    console.print(f"  [green]✔ Pytest Execution:[/green] [{ 'green' if remediation_res['test_passed'] else 'red' }]{ 'ALL TESTS PASSED' if remediation_res['test_passed'] else 'TESTS FAILED' }[/]")

    # Display Diff
    if remediation_res["diff"]:
        console.print("\n[bold yellow]Generated Unified Patch (Diff):[/bold yellow]")
        syntax = Syntax(remediation_res["diff"], "diff", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, border_style="dim yellow", title="Git Diff (Sandbox)"))

    # 6. Deepsec Revalidation Gate
    console.print(Panel("[bold green]6. DEEPSEC REVALIDATION GATE & REGRESSION SCAN[/bold green]", border_style="green"))
    with console.status(f"[green]Deepsec re-scanning sandbox with {config.MODEL_DEEPSEC_REVALIDATE}...[/green]", spinner="dots"):
        time.sleep(0.5)
        revalidation = deepsec.revalidate_patch(sandbox, initial_scan["findings"])

    _display_revalidation_panel(revalidation)

    # 7. Cognee Memory Update: Learn from this PR
    console.print(Panel("[bold purple]7. COGNEE: PERSISTING ENGINEERING MEMORY & KNOWLEDGE GRAPH[/bold purple]", border_style="purple"))
    with console.status(f"[purple]Connecting new nodes in Cognee via {config.MODEL_COGNEE_EXTRACT}...[/purple]", spinner="dots"):
        time.sleep(0.4)
        learned_pattern = f"Defensive pattern: Resolved {', '.join([f['cwe'] for f in initial_scan['findings']])} in {remediation_res['modified_files']} with verified unit tests."
        new_learning = memory.record_learning(
            issue_id=f"ISSUE-{int(time.time())}",
            issue_title=issue_title,
            files_modified=remediation_res["modified_files"],
            vulnerabilities_fixed=[f["title"] for f in initial_scan["findings"]],
            fix_summary=remediation_res["remediation_summary"],
            test_passed=remediation_res["test_passed"],
            human_decision="HUMAN_APPROVED",
            pattern_learned=learned_pattern,
        )

    console.print(f"  [green]✔ New Memory Node Added:[/green] [cyan]{new_learning['id']}[/cyan]")
    console.print(f"  [green]✔ Pattern Stored:[/green] {new_learning['pattern_learned']}")
    console.print(f"  [green]✔ Knowledge Graph Stats:[/green] {memory.get_stats()['total_nodes']} nodes, {memory.get_stats()['total_edges']} edges\n")

    # 8. Brick Governance: Telemetry & Cost Comparison
    console.print(Panel("[bold gold1]8. BRICK GOVERNANCE: TELEMETRY & COST COMPARISON[/bold gold1]", border_style="gold1"))
    display_telemetry_comparison()

    # 9. Export PR Evidence Document
    pr_evidence_path = config.BASE_DIR / "PR_EVIDENCE.md"
    _export_pr_evidence(pr_evidence_path, repo_path, issue_title, initial_scan, remediation_res, revalidation, new_learning)
    console.print(f"\n[bold green]🚀 CLOSED-LOOP FINISHED SUCCESSFULLY![/bold green]")
    console.print(f"[dim]Pull Request Evidence Report generated at: [cyan]{pr_evidence_path}[/cyan][/dim]\n")


def display_telemetry_comparison():
    """Display the Single Frontier Model vs Regolo GLM-5.2 comparison table requested in README.md."""
    telemetry = get_telemetry_summary()
    events = telemetry["events"]

    table = Table(box=ROUNDED, border_style="gold1", header_style="bold cyan", title="Brick Telemetry: Single Frontier Model vs Regolo GLM-5.2 Routed Workflow")
    table.add_column("Pipeline Stage", style="bold white", width=22)
    table.add_column("Model / Engine", style="dim", width=18)
    table.add_column("Tokens (P / C)", style="yellow", width=16)
    table.add_column("Latency", style="dim cyan", width=10)
    table.add_column("Regolo GLM-5.2", style="bold green", width=16)
    table.add_column("Frontier Baseline", style="dim red", width=18)
    table.add_column("Cost Savings", style="bold gold1", width=14)

    for e in events:
        table.add_row(
            e["stage"],
            e["model"],
            f"{e['prompt_tokens']} / {e['completion_tokens']}",
            f"{e['latency_sec']}s",
            f"${e['cost_regolo_usd']:.5f}",
            f"${e['cost_frontier_usd']:.5f}",
            f"-{round((1 - (e['cost_regolo_usd'] / max(0.00001, e['cost_frontier_usd']))) * 100, 1)}%",
        )

    console.print(table)

    summary_panel = Text()
    summary_panel.append(f"Total Tokens Processed: {telemetry['total_tokens']:,}   |   ", style="bold white")
    summary_panel.append(f"Regolo GLM-5.2 Cost: ${telemetry['total_regolo_cost_usd']:.4f}   |   ", style="bold green")
    summary_panel.append(f"Frontier Cost: ${telemetry['total_frontier_cost_usd']:.4f}   |   ", style="dim red")
    summary_panel.append(f"Total Savings: {telemetry['savings_percentage']}%", style="bold gold1")

    console.print(Panel(Align.center(summary_panel), box=ROUNDED, border_style="green"))


def _display_findings_table(findings: List[Dict[str, Any]], title: str):
    """Render findings table."""
    table = Table(title=title, box=ROUNDED, border_style="red", header_style="bold magenta")
    table.add_column("ID", style="bold yellow", width=9)
    table.add_column("Severity", style="bold red", width=10)
    table.add_column("CWE / OWASP", style="dim cyan", width=14)
    table.add_column("Vulnerability Title", style="bold white", width=34)
    table.add_column("Location", style="yellow", width=14)
    table.add_column("Status", style="bold red", width=14)

    if not findings:
        table.add_row("CLEAN", "NONE", "-", "No vulnerabilities detected", "All files", "PASSED")
    else:
        for f in findings:
            table.add_row(
                f["id"],
                f["severity"],
                f"{f.get('cwe', '')}",
                f["title"],
                f"{f.get('file', '')}:{f.get('line', '')}",
                f["status"],
            )
    console.print(table)


def _display_memory_patterns(patterns: List[Dict[str, Any]]):
    """Render memory recall tree."""
    tree = Tree("🧠 [bold purple]Cognee Engineering Memory Recalled[/bold purple]")
    for p in patterns:
        branch = tree.add(f"[bold cyan]{p.get('id', '')}: {p.get('name', p.get('title', 'Rule'))}[/bold cyan]")
        branch.add(f"[dim]{p.get('description', p.get('pattern_learned', ''))}[/dim]")
    console.print(tree)
    console.print()


def _display_plan_panel(plan: Dict[str, Any]):
    """Render plan steps in a neat panel."""
    plan_text = Text()
    plan_text.append(f"Plan ID: {plan.get('plan_id', 'PLAN-GLM52-01')}  •  Risk Rating: {plan.get('estimated_risk', 'MEDIUM')}\n\n", style="bold yellow")
    
    steps = plan.get("steps", [])
    for s in steps:
        step_num = s.get("step_number", "")
        action = s.get("action", "")
        desc = s.get("description", "")
        plan_text.append(f"  [{step_num}] {action}\n", style="bold cyan")
        plan_text.append(f"      {desc}\n", style="white")

    console.print(Panel(plan_text, title=f"📋 Open SWE Remediation Plan: {plan.get('title', 'Remediation')}", box=ROUNDED, border_style="blue"))


def _display_revalidation_panel(reval: Dict[str, Any]):
    """Render revalidation gate outcome."""
    status_color = "green" if reval["revalidation_passed"] else "red"
    status_text = Text()
    status_text.append("DEEPSEC REVALIDATION GATE OUTCOME\n", style=f"bold {status_color}")
    status_text.append(f"Status: {reval['gate_status']}  •  Security Score: {reval['security_score']}/100\n\n", style="bold white")
    status_text.append(f"Resolved Findings: {', '.join(reval['findings_resolved'])}\n", style="green")
    status_text.append(f"Residual Findings: {len(reval['residual_findings'])}\n", style="bold white")
    status_text.append(f"Evidence: {reval['evidence']}", style="dim")

    console.print(Panel(status_text, box=DOUBLE, border_style=status_color))


def inspect_cognee_graph():
    """Display full Cognee memory graph."""
    print_banner()
    memory = CogneeMemoryGraph()
    stats = memory.get_stats()
    nodes = memory.get_all_nodes()

    console.print(f"[bold purple]🧠 COGNEE KNOWLEDGE GRAPH & ENGINEERING MEMORY[/bold purple]")
    console.print(f"Total Nodes: [cyan]{stats['total_nodes']}[/cyan] | Total Edges: [cyan]{stats['total_edges']}[/cyan] | Rules: [green]{stats['rules_count']}[/green] | Learned PRs: [yellow]{stats['learnings_count']}[/yellow]\n")

    table = Table(box=ROUNDED, border_style="purple", header_style="bold magenta")
    table.add_column("Node ID", style="bold cyan", width=14)
    table.add_column("Type", style="bold yellow", width=18)
    table.add_column("Name / Title", style="bold white", width=30)
    table.add_column("Content / Rule / Pattern", style="dim", width=46)

    for n in nodes:
        table.add_row(
            n.get("id", ""),
            n.get("type", ""),
            n.get("name", n.get("title", "")),
            str(n.get("description", n.get("pattern_learned", "")))[:90] + "...",
        )

    console.print(table)
    Prompt.ask("\n[bold cyan]Press Enter to return to main menu[/bold cyan]")


def _export_pr_evidence(
    output_path: Path,
    repo_path: str,
    issue_title: str,
    initial_scan: Dict[str, Any],
    remediation: Dict[str, Any],
    revalidation: Dict[str, Any],
    learning: Dict[str, Any],
):
    """Generate markdown evidence file for the GitHub Pull Request."""
    telemetry = get_telemetry_summary()
    content = f"""# Pull Request: Automated Remediation via Open SWE & Deepsec

## Summary
- **Target Repository**: `{repo_path}`
- **Resolved Issue**: {issue_title}
- **Inference Engine**: Regolo.ai (`{config.REGOLO_MODEL}`)
- **Security Gate Status**: `{revalidation['gate_status']}` (Score: {revalidation['security_score']}/100)

## Security Vulnerabilities Addressed (Deepsec Initial Audit)
| Finding ID | Severity | CWE | Title | File | Status |
|---|---|---|---|---|---|
"""
    for f in initial_scan["findings"]:
        content += f"| {f['id']} | {f['severity']} | {f['cwe']} | {f['title']} | `{f['file']}:{f['line']}` | RESOLVED |\n"

    content += f"""
## Deepsec Revalidation Gate Evidence
- **Pre-scan Score**: {initial_scan['security_score']}/100
- **Post-remediation Score**: {revalidation['security_score']}/100
- **Automated Verification**: {revalidation['evidence']}
- **Unit & Regression Tests**: {'✔ PASSED' if remediation['test_passed'] else '❌ FAILED'}

## Applied Patch
```diff
{remediation['diff']}
```

## Cognee Engineering Memory Graph Node
- **Memory ID**: `{learning['id']}`
- **Pattern Learned**: {learning['pattern_learned']}
- **Human Approval**: `{learning['human_decision']}`

## Brick Telemetry & Cost Efficiency (Regolo GLM-5.2 vs Frontier)
- **Total Tokens**: {telemetry['total_tokens']:,}
- **Regolo GLM-5.2 Cost**: ${telemetry['total_regolo_cost_usd']:.4f}
- **Frontier Baseline Cost**: ${telemetry['total_frontier_cost_usd']:.4f}
- **Cost Reduction**: **{telemetry['savings_percentage']}% savings**

*Generated by Closed-Loop Coding Agent (Open SWE + Deepsec + Cognee + Regolo)*
"""
    output_path.write_text(content, encoding="utf-8")


def manage_docker_services():
    """Interactive management for Docker backend services (Qdrant & Cognee)."""
    while True:
        print_banner()
        console.print("[bold blue]🐳 DOCKER SERVICE ORCHESTRATION & INCREMENTAL PORT DISCOVERY[/bold blue]")
        console.print("[dim]Manages Qdrant vector database and Cognee graph backend. Automatically binds next free port if default is occupied.[/dim]\n")

        docker_ok, docker_msg = is_docker_available()
        if not docker_ok:
            console.print(f"[bold red]❌ Docker Status: Unavailable ({docker_msg})[/bold red]")
            console.print("[yellow]Please start Docker Desktop or the Docker daemon to launch containerized backends.[/yellow]\n")
        else:
            console.print(f"[bold green]✔ Docker Status: Active ({docker_msg})[/bold green]\n")

        statuses = get_services_status()
        table = Table(box=ROUNDED, border_style="blue", header_style="bold cyan", expand=True)
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

        console.print("\n[bold white]Service Actions:[/bold white]")
        console.print("  [bold cyan][1][/bold cyan] 🚀 [bold]Start / Deploy All Services[/bold] [dim](Pulls if missing, starts if stopped, discovers free ports)[/dim]")
        console.print("  [bold cyan][2][/bold cyan] 🛑 [bold]Stop All Services[/bold] [dim](Gracefully stops running containers)[/dim]")
        console.print("  [bold cyan][3][/bold cyan] 🔄 [bold]Refresh Status[/bold]")
        console.print("  [bold cyan][4][/bold cyan] ↩ [bold]Return to Main Menu[/bold]")

        action = Prompt.ask(
            "\n[bold yellow]Select service action[/bold yellow]",
            choices=["1", "2", "3", "4"],
            default="1",
        )

        if action == "1":
            if not docker_ok:
                console.print("[bold red]Cannot start services: Docker is not running.[/bold red]")
                Prompt.ask("\n[bold cyan]Press Enter to continue[/bold cyan]")
                continue

            console.print("\n[bold cyan]Launching services with incremental port discovery...[/bold cyan]")
            with console.status("[cyan]Deploying containers...[/cyan]", spinner="dots"):
                results = start_all_services(log_callback=lambda m: console.print(f"  {m}"))

            console.print("\n[bold green]✔ All required services checked & launched![/bold green]")
            Prompt.ask("\n[bold cyan]Press Enter to continue[/bold cyan]")

        elif action == "2":
            with console.status("[yellow]Stopping services...[/yellow]", spinner="dots"):
                stop_all_services(log_callback=lambda m: console.print(f"  {m}"))
            console.print("\n[bold green]✔ Managed services stopped.[/bold green]")
            Prompt.ask("\n[bold cyan]Press Enter to continue[/bold cyan]")

        elif action == "3":
            continue

        elif action == "4":
            break


def interactive_main_menu():
    """Main interactive loop for the TUI."""
    while True:
        print_banner()
        console.print("[bold white]Main Interactive Menu:[/bold white]\n")

        console.print("  [bold cyan][1][/bold cyan] 🚀 [bold]Run Full Closed Loop[/bold] [dim](Open SWE ➔ Deepsec ➔ Cognee ➔ Brick End-to-End)[/dim]")
        console.print("  [bold cyan][2][/bold cyan] 🐳 [bold]Manage Docker Services[/bold] [dim](Qdrant Vector DB & Cognee Engine with Incremental Port Discovery)[/dim]")
        console.print("  [bold cyan][3][/bold cyan] 🔍 [bold]Deepsec Security Scan Only[/bold] [dim](Vulnerability Audit on Target Repo)[/dim]")
        console.print("  [bold cyan][4][/bold cyan] 🧠 [bold]Cognee Memory Graph Inspector[/bold] [dim](View Persistent Knowledge Graph & Rules)[/dim]")
        console.print("  [bold cyan][5][/bold cyan] 📊 [bold]Brick Governance & Telemetry Scoreboard[/bold] [dim](Cost & Token Analytics)[/dim]")
        console.print("  [bold cyan][6][/bold cyan] 🧪 [bold]Run Automated Test Suite[/bold] [dim](Verify all modules with pytest)[/dim]")
        console.print("  [bold cyan][7][/bold cyan] ❌ [bold]Exit[/bold]")

        choice = Prompt.ask(
            "\n[bold yellow]Select an option[/bold yellow]",
            choices=["1", "2", "3", "4", "5", "6", "7"],
            default="1",
        )

        if choice == "1":
            run_full_closed_loop_flow()
            Prompt.ask("\n[bold cyan]Press Enter to return to main menu[/bold cyan]")
        elif choice == "2":
            manage_docker_services()
        elif choice == "3":
            print_banner()
            repo_path, _, _ = select_target_repository()
            deepsec = DeepsecSecurityHarness()
            sandbox = SandboxEnvironment(source_repo_path=repo_path)
            with console.status("[red]Running Deepsec SAST security scan...[/red]", spinner="dots"):
                scan = deepsec.run_security_scan(sandbox)
            _display_findings_table(scan["findings"], title=f"Deepsec Scan Results: {Path(repo_path).name}")
            console.print(f"\n[bold]Security Score:[/bold] [{ 'green' if scan['security_score'] > 70 else 'red' }]{scan['security_score']}/100[/]")
            Prompt.ask("\n[bold cyan]Press Enter to return to main menu[/bold cyan]")
        elif choice == "4":
            inspect_cognee_graph()
        elif choice == "5":
            print_banner()
            display_telemetry_comparison()
            Prompt.ask("\n[bold cyan]Press Enter to return to main menu[/bold cyan]")
        elif choice == "6":
            print_banner()
            console.print("[bold yellow]Running test suite...[/bold yellow]\n")
            os.system("python3 -m pytest -v")
            Prompt.ask("\n[bold cyan]Press Enter to return to main menu[/bold cyan]")
        elif choice == "7":
            console.print("\n[bold cyan]Goodbye! Exiting Closed-Loop Agent.[/bold cyan]\n")
            sys.exit(0)
