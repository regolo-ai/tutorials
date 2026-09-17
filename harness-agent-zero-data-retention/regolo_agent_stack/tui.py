import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich import box

from .config import REGOLO_MODEL, REGOLO_BASE_URL
from .cli import (
    cmd_doctor,
    cmd_eval,
    cmd_review,
    cmd_fix,
    cmd_services,
    TASK_PROMPT,
)
from .context import list_git_branches
from .services import (
    check_system_environment,
    is_port_in_use,
    find_available_port,
    get_running_service_info,
    start_local_report_service,
    stop_local_report_service,
)

BRAND_GREEN = "#00FF88"
console = Console()

ASCII_LOGO = """
 ██████╗  ███████╗  ██████╗   ██████╗  ██╗       ██████╗ 
 ██╔══██╗ ██╔════╝ ██╔════╝  ██╔═══██╗ ██║      ██╔═══██╗
 ██████╔╝ █████╗   ██║  ███╗ ██║   ██║ ██║      ██║   ██║
 ██╔══██╗ ██╔══╝   ██║   ██║ ██║   ██║ ██║      ██║   ██║
 ██║  ██║ ███████╗ ╚██████╔╝ ╚██████╔╝ ███████╗ ╚██████╔╝
 ╚═╝  ╚═╝ ╚══════╝  ╚═════╝   ╚═════╝  ╚══════╝  ╚═════╝ 
"""

def print_header(port: int = 8080):
    header_text = Text()
    header_text.append(ASCII_LOGO.strip("\n"), style=f"bold {BRAND_GREEN}")
    header_text.append("\n\n")
    header_text.append("       HARNESS ENGINEERING  ·  OPEN MODELS  ·  EU ZERO DATA RETENTION\n", style="bold white")
    header_text.append(f"       Endpoint: {REGOLO_BASE_URL}  ·  Model: {REGOLO_MODEL}  ·  Port: {port}", style="dim green")

    banner_panel = Panel(
        header_text,
        box=box.HEAVY,
        border_style=BRAND_GREEN,
        padding=(1, 2),
    )
    console.print(banner_panel)

def menu():
    t = Table(
        box=box.ROUNDED,
        border_style=BRAND_GREEN,
        title="  ⚡ MAIN CONTROL PANEL  ",
        title_style=f"bold {BRAND_GREEN}",
        expand=True,
    )
    t.add_column("Key", style=f"bold {BRAND_GREEN}", width=6, justify="center")
    t.add_column("Action", style="bold white", width=34)
    t.add_column("Scope / Details", style="dim")

    t.add_row("1", "Environment & API Check", "Verify Python, Docker, Node & Regolo ZDR API")
    t.add_row("2", "Run Live A/B Benchmark", "Head-to-head lift: Harness A (baseline) vs Harness B (optimized)")
    t.add_row("3", "Review & Auto-Fix Repository", "Scan git diff against base branch, detect leaks & apply fixes")
    t.add_row("4", "Direct Code Auto-Fix", "Isolate modified files and directly apply AI-generated patches")
    t.add_row("5", "Start / Stop Dashboard Server", "Launch or stop local HTTP report server on port 8080")
    t.add_row("6", "Exit", "Safely terminate background services and exit to terminal")
    console.print(t)

def main():
    service_port = 8080
    if is_port_in_use(service_port):
        service_port = find_available_port(service_port + 1)

    try:
        while True:
            console.clear()
            print_header(service_port)
            menu()

            console.print(Panel(
                f"[bold white]SELECT AN OPTION [1 - 6][/bold white]\n"
                f"[dim]• Press [bold {BRAND_GREEN}]2[/bold {BRAND_GREEN}] or hit [bold white]ENTER[/bold white] to run the Live A/B Benchmark[/dim]\n"
                f"[dim]• Press [bold {BRAND_GREEN}]3[/bold {BRAND_GREEN}] to review and auto-fix an external repository[/dim]",
                box=box.ROUNDED,
                border_style=BRAND_GREEN,
                padding=(0, 2),
            ))

            choice = Prompt.ask(
                f"[bold {BRAND_GREEN}]➤ Select Option[/bold {BRAND_GREEN}]",
                choices=["1", "2", "3", "4", "5", "6"],
                default="2",
            )

            if choice == "1":
                cmd_doctor(None)
                Prompt.ask("[dim]Press Enter to continue...[/dim]")

            elif choice == "2":
                class Args:
                    model = None
                    runs = 2
                cmd_eval(Args())
                Prompt.ask("[dim]Press Enter to continue...[/dim]")

            elif choice == "3":
                console.print(Panel(
                    "[bold]Paste the target project path to review (absolute or relative):[/bold]\n"
                    "[dim]• Example: /Users/username/projects/my-app\n"
                    "• Press Enter directly to inspect the current folder ('.')[/dim]",
                    border_style=BRAND_GREEN,
                ))
                raw_path = Prompt.ask(f"[{BRAND_GREEN}]Project path[/{BRAND_GREEN}]", default=".")
                clean_path = raw_path.strip().strip("'\"")
                target_path = Path(clean_path).expanduser().resolve()
                if not target_path.exists() or not target_path.is_dir():
                    console.print(f"\n[bold red]❌ Target directory does not exist:[/bold red] {target_path}")
                    Prompt.ask("\n[dim]Press Enter to continue...[/dim]")
                    continue

                curr_branch, branches = list_git_branches(target_path)
                selected_branch = None

                if branches:
                    b_table = Table(
                        box=box.ROUNDED,
                        border_style=BRAND_GREEN,
                        title=f"GIT BRANCHES IN '{target_path.name}'",
                        title_style=f"bold {BRAND_GREEN}",
                    )
                    b_table.add_column("#", style=f"bold {BRAND_GREEN}", width=4)
                    b_table.add_column("Branch", style="bold white")
                    b_table.add_column("Role / Status", style="dim")

                    default_idx = 1
                    for idx, b in enumerate(branches, 1):
                        badges = []
                        if b == curr_branch:
                            badges.append("[green]● current active branch[/green]")
                        if b in ("main", "master", "origin/main", "origin/master"):
                            badges.append("[yellow](recommended base for diff)[/yellow]")
                            if default_idx == 1 and b != curr_branch:
                                default_idx = idx
                        b_table.add_row(str(idx), b, " · ".join(badges) if badges else "branch")

                    console.print()
                    console.print(b_table)
                    console.print("[dim]Select the target base branch to compute the diff against.[/dim]")
                    pick = Prompt.ask(
                        f"[{BRAND_GREEN}]Reference branch (number or name)[/{BRAND_GREEN}]",
                        default=str(default_idx),
                    )

                    if pick.isdigit() and 1 <= int(pick) <= len(branches):
                        selected_branch = branches[int(pick) - 1]
                    elif pick in branches:
                        selected_branch = pick
                    else:
                        selected_branch = pick.strip()

                    console.print(f"\n[{BRAND_GREEN}]✓ Base branch set to:[/{BRAND_GREEN}] [bold white]{selected_branch}[/bold white]\n")

                class Args:
                    path = str(target_path)
                    scope = "branch" if selected_branch else "staged"
                    branch = selected_branch
                    base = selected_branch or "origin/main"
                    interactive = True

                cmd_review(Args())
                Prompt.ask("\n[dim]Press Enter to continue...[/dim]")

            elif choice == "4":
                console.print(Panel(
                    "[bold]Direct Auto-Fix: Paste the repository path to remediate:[/bold]\n"
                    "[dim]• Press Enter directly to use current directory ('.')[/dim]",
                    border_style=BRAND_GREEN,
                ))
                raw_path = Prompt.ask(f"[{BRAND_GREEN}]Project path[/{BRAND_GREEN}]", default=".")
                clean_path = raw_path.strip().strip("'\"")
                target_path = Path(clean_path).expanduser().resolve()
                if not target_path.exists() or not target_path.is_dir():
                    console.print(f"\n[bold red]❌ Target directory does not exist:[/bold red] {target_path}")
                    Prompt.ask("\n[dim]Press Enter to continue...[/dim]")
                    continue

                curr_branch, branches = list_git_branches(target_path)
                selected_branch = None
                if branches and len(branches) > 1:
                    default_branch = "main" if "main" in branches else ("master" if "master" in branches else branches[0])
                    pick = Prompt.ask(f"[{BRAND_GREEN}]Base branch (default: {default_branch})[/{BRAND_GREEN}]", default=default_branch)
                    selected_branch = pick.strip()

                class Args:
                    path = str(target_path)
                    scope = "branch" if selected_branch else "staged"
                    branch = selected_branch
                    base = selected_branch or "origin/main"
                    apply = False
                    interactive = True

                cmd_fix(Args())
                Prompt.ask("\n[dim]Press Enter to continue...[/dim]")

            elif choice == "5":
                info = get_running_service_info()
                if info:
                    console.print(Panel(
                        f"[bold green]● Dashboard Server is currently RUNNING[/bold green]\n"
                        f"• URL: [bold cyan]{info['url']}[/bold cyan]\n"
                        f"• Process PID: [dim]{info['pid']}[/dim]\n\n"
                        f"[dim]You can open the URL above in your web browser to view all benchmark and review reports.[/dim]",
                        border_style=BRAND_GREEN,
                    ))
                    stop_it = Prompt.ask(f"[{BRAND_GREEN}]Do you want to stop the dashboard server? [y/N][/{BRAND_GREEN}]", default="n").strip().lower()
                    if stop_it in ("y", "yes", "s", "si"):
                        stop_local_report_service()
                        console.print("\n[bold green]✅ Dashboard server stopped successfully.[/bold green]\n")
                else:
                    console.print(Panel(
                        f"[bold yellow]○ Dashboard Server is currently STOPPED[/bold yellow]\n\n"
                        f"Starts a local HTTP server displaying interactive HTML reports and benchmarks.\n"
                        f"Port: [cyan]{service_port}[/cyan] (automatically resolves port conflicts).",
                        border_style=BRAND_GREEN,
                    ))
                    start_it = Prompt.ask(f"[{BRAND_GREEN}]Start the dashboard server now? [Y/n][/{BRAND_GREEN}]", default="y").strip().lower()
                    if start_it in ("", "y", "yes", "s", "si"):
                        info = start_local_report_service(service_port)
                        service_port = info["port"]
                        console.print(f"\n[bold green]✅ Dashboard Server is active at:[/bold green] [bold cyan]{info['url']}[/bold cyan]\n")

                Prompt.ask("[dim]Press Enter to continue...[/dim]")

            elif choice == "6":
                console.print("\n[dim]Closing Regolo TUI. Goodbye![/dim]\n")
                sys.exit(0)

    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]Session interrupted by user (CTRL+C). Goodbye![/bold yellow]\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
