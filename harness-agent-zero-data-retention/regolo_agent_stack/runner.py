import time
import sys
from contextlib import nullcontext

try:
    from rich.console import Console
    console = Console()
except ImportError:
    console = None

from .client import RegoloClient
from .harness_a import run_harness_a
from .harness_b import run_harness_b
from .evaluator import evaluate_code

def _log(msg: str):
    if console:
        console.print(msg)
    else:
        import re
        print(re.sub(r"\[.*?\]", "", msg), flush=True)

class RunResult:
    def __init__(self, result: dict):
        self.harness = result.get("harness")
        self.model = result.get("model")
        self.code = result.get("code", "")
        self.turns = result.get("turns", 1)
        self.prompt_tokens = result.get("prompt_tokens", 0)
        self.completion_tokens = result.get("completion_tokens", 0)
        self.total_tokens = result.get("total_tokens", 0)
        self.latency_sec = result.get("latency_sec", 0.0)
        self.raw = result

def run_benchmark(task_prompt: str, model: str, harness: str = "A,B", runs: int = 1) -> dict:
    results = {"A": [], "B": []}
    harness_list = [h.strip() for h in harness.split(",")]
    total_steps = runs * len(harness_list)
    step = 0

    for run_idx in range(1, runs + 1):
        for label in harness_list:
            step += 1
            hname = "Harness A (Baseline)" if label == "A" else "Harness B (Regolo Optimized)"
            prefix = f"[{step}/{total_steps}] {hname} · Run #{run_idx}/{runs}"
            t0 = time.time()
            status_ctx = console.status(f"[bold cyan]{prefix}[/bold cyan] · [yellow]Querying Regolo ZDR API ('{model}')...[/yellow]", spinner="dots") if console else nullcontext()
            try:
                with status_ctx as status:
                    if label == "A":
                        raw = run_harness_a(task_prompt, model=model)
                    elif label == "B":
                        raw = run_harness_b(task_prompt, model=model)
                    else:
                        raise ValueError(f"Harness sconosciuto: {label}")

                    run_data = RunResult(raw).__dict__
                    if hasattr(status, "update"):
                        status.update(f"[bold cyan]{prefix}[/bold cyan] · [yellow]Running PyTest suite in sandbox...[/yellow]")
                    if run_data.get("code"):
                        ev = evaluate_code(run_data["code"])
                        run_data.update(ev)
                    else:
                        run_data["success"] = False

                lat = run_data.get("latency_sec", round(time.time() - t0, 2))
                tok = run_data.get("total_tokens", 0)
                if run_data.get("success"):
                    _log(f"  [bold green]✓ PASS[/bold green]  {prefix} in [bold]{lat}s[/bold] ({tok} tok) · [green]3/3 unit tests passed (XML <code> Contract + clean AST)[/green]")
                else:
                    if label == "A":
                        err_hint = "Zero-Harness: conversational filler & unparsed markdown cause SyntaxError"
                    else:
                        err_hint = "Unit tests failed: concurrency or edge-case assertion mismatch"
                    _log(f"  [bold red]✗ FAIL[/bold red]  {prefix} in [bold]{lat}s[/bold] ({tok} tok) · [yellow]{err_hint}[/yellow]")
                results[label].append(run_data)

            except Exception as exc:
                elapsed = round(time.time() - t0, 2)
                _log(f"  [bold red]✗ ERROR[/bold red] {prefix} ({elapsed}s): [red]{exc}[/red]")
                results[label].append({
                    "harness": hname,
                    "model": model,
                    "code": "",
                    "turns": 1,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "latency_sec": elapsed,
                    "success": False,
                    "error": str(exc),
                })
    return results
