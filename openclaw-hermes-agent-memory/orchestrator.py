#!/usr/bin/env python3
import json
import os
import subprocess
import time
from pathlib import Path

import psutil
from rich.console import Console
from rich.table import Table

console = Console()

NUM_EVENTS = 300
OC_SESSION_ID = "benchmark_oc_v1"
HR_SESSION_ID = "benchmark_hr_v1"

OC_STATE_DIR = Path.home() / ".openclaw"
HR_STATE_DIR = Path.home() / ".hermes"

def make_events(n: int) -> list[dict]:
    events = []
    for i in range(1, n + 1):
        events.append({
            "id": i,
            "ticket": f"TICKET-{i:04d}",
            "text": f"TICKET-{i:04d}: A customer reported a billing anomaly. Fixed in {(i%9)+2} mins."
        })
    return events

def get_daemon_pid(process_name_hints: list[str]) -> int | None:
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            for hint in process_name_hints:
                if hint in cmdline and "orchestrator.py" not in cmdline:
                    return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def get_rss_mb(pid: int) -> float:
    if not pid: return 0.0
    try: return psutil.Process(pid).memory_info().rss / 1024 / 1024
    except psutil.NoSuchProcess: return 0.0

def get_dir_size_bytes(directory: Path) -> int:
    if not directory.exists(): return 0
    total = 0
    for root, _, files in os.walk(directory):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp): total += os.path.getsize(fp)
    return total

def run_benchmark():
    events = make_events(NUM_EVENTS)
    oc_pid = get_daemon_pid(["openclaw", "gateway"])
    hr_pid = get_daemon_pid(["hermes", "gateway", "start"])
        
    oc_start_rss = get_rss_mb(oc_pid) if oc_pid else 0.0
    hr_start_rss = get_rss_mb(hr_pid) if hr_pid else 0.0
    oc_start_disk = get_dir_size_bytes(OC_STATE_DIR)
    hr_start_disk = get_dir_size_bytes(HR_STATE_DIR)

    console.print(f"\n[bold cyan]Starting real injection of {NUM_EVENTS} events...[/bold cyan]")
    
    t0 = time.perf_counter()
    for e in events:
        console.print(f"  [yellow]Injecting {e['ticket']} -> OpenClaw[/yellow]")
        subprocess.run(["openclaw", "agent", "--local", "--session-id", OC_SESSION_ID, "-m", e["text"], "--json"], check=False)
        
        console.print(f"  [yellow]Injecting {e['ticket']} -> Hermes[/yellow]")
        subprocess.run(["hermes", "chat", "-q", e["text"], "-Q", "--continue", HR_SESSION_ID], check=False)
    
    build_time = time.perf_counter() - t0
    console.print(f"  [green]Done injecting in {build_time:.2f}s[/green]\n")

    time.sleep(2)
    recall_prompt = "What was the exact outcome and fix pattern for TICKET-0002?"
    console.print("[bold cyan]Testing Recall Latency...[/bold cyan]")
    
    rt0 = time.perf_counter()
    subprocess.run(["openclaw", "agent", "--local", "--session-id", OC_SESSION_ID, "-m", recall_prompt, "--json"], check=False)
    oc_recall_ms = (time.perf_counter() - rt0) * 1000
    
    rt0 = time.perf_counter()
    subprocess.run(["hermes", "chat", "-q", recall_prompt, "-Q", "--continue", HR_SESSION_ID], check=False)
    hr_recall_ms = (time.perf_counter() - rt0) * 1000

    oc_end_rss = get_rss_mb(oc_pid) if oc_pid else 0.0
    hr_end_rss = get_rss_mb(hr_pid) if hr_pid else 0.0
    oc_disk_delta = get_dir_size_bytes(OC_STATE_DIR) - oc_start_disk
    hr_disk_delta = get_dir_size_bytes(HR_STATE_DIR) - hr_start_disk

    table = Table(title=f"Live Architecture Benchmark ({NUM_EVENTS} events)", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("OpenClaw", justify="right")
    table.add_column("Hermes Agent", justify="right")
    table.add_row("RSS Memory Δ", f"{(oc_end_rss - oc_start_rss):.2f} MB", f"{(hr_end_rss - hr_start_rss):.2f} MB")
    table.add_row("Disk Usage Δ", f"{(oc_disk_delta / 1024):.2f} KB", f"{(hr_disk_delta / 1024):.2f} KB")
    table.add_row("Recall Latency", f"{oc_recall_ms:.2f} ms", f"{hr_recall_ms:.2f} ms")
    console.print("")
    console.print(table)

if __name__ == "__main__":
    run_benchmark()
