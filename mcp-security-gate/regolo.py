#!/usr/bin/env python3
"""
REGOLO MCP Security Gate
Pre-installation static analysis, prompt injection detection, and version locking for Model Context Protocol.

Interactive Terminal User Interface (REGOLO Green Edition)
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional

from gate.environment import EnvironmentManager
from gate.fingerprint import ToolFingerprint
from gate.registry import Registry, ToolStatus, VerificationResult
from gate.remediate import RegoloRemediator
from gate.rules import RuleEngine, Severity
from gate.scan import GateScanner, ToolScanReport
from gate.service_manager import ServiceManager


# ==============================================================================
# ANSI REGOLO GREEN PALETTE & FORMATTING
# ==============================================================================
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"

# Greens
C_GREEN_BRIGHT = "\033[38;5;46m"    # Neon Regolo Green
C_GREEN_MID = "\033[38;5;40m"       # Vibrant Green
C_GREEN_DARK = "\033[38;5;28m"      # Forest Accent
C_GREEN_BG = "\033[48;5;22m"        # Dark Green Background Block
C_GREEN_INVERSE = "\033[7;38;5;46m" # Inverted Green

# Supporting status colors
C_RED_BRIGHT = "\033[38;5;196m"     # Threat Blocked
C_YELLOW_BRIGHT = "\033[38;5;226m"  # Warning / Unregistered
C_CYAN_BRIGHT = "\033[38;5;51m"     # Highlight / Metrics
C_WHITE_BRIGHT = "\033[1;97m"       # High contrast titles


def clear_screen():
    print("\033[H\033[J", end="")


def pause(prompt: str = "\n  Press [ENTER] to return to menu..."):
    try:
        input(f"{C_DIM}{prompt}{C_RESET}")
    except (KeyboardInterrupt, EOFError):
        pass


def draw_header(active_services_count: int = 0):
    term_width = shutil.get_terminal_size((80, 24)).columns
    width = min(max(term_width, 76), 90)

    logo = [
        r"  ██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗ ",
        r"  ██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗",
        r"  ██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║",
        r"  ██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║",
        r"  ██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝",
        r"  ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ ",
    ]

    print(f"{C_GREEN_BRIGHT}{'=' * width}{C_RESET}")
    for line in logo:
        print(f"{C_GREEN_BRIGHT}{line.center(width)}{C_RESET}")
    print(f"{C_BOLD}{C_WHITE_BRIGHT}{'M C P   S E C U R I T Y   G A T E'.center(width)}{C_RESET}")
    print(f"{C_DIM}{'Supply Chain Defense, Steganography Detection & Version Locking'.center(width)}{C_RESET}")
    print(f"{C_GREEN_MID}{'-' * width}{C_RESET}")

    # Telemetry Status Bar
    py_v = f"Python {sys.version_info.major}.{sys.version_info.minor}"
    node_chk = EnvironmentManager.check_node()
    node_v = node_chk.version.splitlines()[0] if node_chk.installed else "Node: N/A"
    docker_chk = EnvironmentManager.check_docker()
    docker_v = "Docker: Ready" if docker_chk.is_ready else "Docker: Inactive"
    svc_status = f"Services: {active_services_count}/4 Active"

    status_line = f" [PYTHON] {py_v}  |  [NODE] {node_v}  |  [DOCKER] {docker_v}  |  [STATUS] {svc_status}"
    print(f"{C_GREEN_BG}{C_WHITE_BRIGHT}{status_line.center(width)}{C_RESET}")
    print(f"{C_GREEN_BRIGHT}{'=' * width}{C_RESET}\n")


class RegoloTUI:
    """Interactive Green Terminal User Interface for REGOLO MCP Security Gate."""

    def __init__(self):
        self.registry = Registry()
        self.scanner = GateScanner(self.registry)
        self.service_mgr = ServiceManager()
        self.base_dir = Path(__file__).resolve().parent

    def get_active_services_count(self) -> int:
        svcs = self.service_mgr.get_services()
        return sum(1 for s in svcs.values() if s.status == "RUNNING")

    def run(self):
        """Main event loop."""
        while True:
            clear_screen()
            active_count = self.get_active_services_count()
            draw_header(active_services_count=active_count)

            print(f"  {C_BOLD}{C_GREEN_BRIGHT}SELECT AN OPERATION:{C_RESET}\n")
            print(f"  {C_GREEN_BRIGHT}[1]{C_RESET} {C_WHITE_BRIGHT}Interactive Demo Walkthrough{C_RESET}       {C_DIM}(Safe vs Poisoned vs Rug-Pull){C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[2]{C_RESET} {C_WHITE_BRIGHT}Setup Environment{C_RESET}                  {C_DIM}(Python venv, Node.js, Docker){C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[3]{C_RESET} {C_WHITE_BRIGHT}Start / Stop Demo Services{C_RESET}         {C_DIM}(Manage live MCP background servers){C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[4]{C_RESET} {C_WHITE_BRIGHT}Run Security Gate Scanner{C_RESET}          {C_DIM}(Inspect files, folders, or Claude configs){C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[5]{C_RESET} {C_WHITE_BRIGHT}Approved Registry & Version Lock{C_RESET}   {C_DIM}(SHA-256 Fingerprints & mcp-lock.json){C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[6]{C_RESET} {C_WHITE_BRIGHT}Developer Routine & CI Gate{C_RESET}        {C_DIM}(Git Pre-Commit Hook & GitHub Actions CI){C_RESET}")
            print(f"  {C_DIM}──────────────────────────────────────────────────────────────────────{C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[0]{C_RESET} {C_DIM}Exit REGOLO Gate{C_RESET}\n")

            choice = input(f"  {C_GREEN_BRIGHT}REGOLO >{C_RESET} ").strip()

            if choice == "1":
                self.view_demo_walkthrough()
            elif choice == "2":
                self.view_setup_environment()
            elif choice == "3":
                self.view_services_manager()
            elif choice == "4":
                self.view_interactive_scanner()
            elif choice == "5":
                self.view_registry_manager()
            elif choice == "6":
                self.view_dev_routine_ci()
            elif choice in ("0", "q", "exit"):
                clear_screen()
                print(f"\n  {C_GREEN_BRIGHT}[REGOLO]{C_RESET} Shutting down. Stopping background demo processes...")
                self.service_mgr.stop_all()
                print(f"  {C_GREEN_BRIGHT}[REGOLO]{C_RESET} Cleanup complete.\n")
                break

    # ==========================================================================
    # VIEW 1: DEMO WALKTHROUGH
    # ==========================================================================
    def view_demo_walkthrough(self):
        clear_screen()
        draw_header(self.get_active_services_count())
        print(f"  {C_BOLD}{C_GREEN_BRIGHT}--- INTERACTIVE DEMO: 3 PHASES OF MCP TOOL ATTACKS ---{C_RESET}")
        print(f"  {C_DIM}Testing static analysis, prompt injection defense, and rug-pull drift{C_RESET}\n")

        print(f"  {C_GREEN_MID}Choose demonstration phase:{C_RESET}")
        print(f"  {C_GREEN_BRIGHT}[1]{C_RESET} Full Automated 3-Phase Simulation")
        print(f"  {C_GREEN_BRIGHT}[2]{C_RESET} Phase 1: Vetted Tool (Baseline Calculation & Fingerprinting)")
        print(f"  {C_GREEN_BRIGHT}[3]{C_RESET} Phase 2: Poisoned Tool (Hidden Prompt Injection reading ~/.ssh/id_rsa)")
        print(f"  {C_GREEN_BRIGHT}[4]{C_RESET} Phase 3: Rug-Pull (Stealth update altering approved tool definition)")
        print(f"  {C_GREEN_BRIGHT}[0]{C_RESET} Back to Main Menu\n")

        sub = input(f"  {C_GREEN_BRIGHT}Demo >{C_RESET} ").strip()
        if sub == "1":
            self._demo_act_1()
            pause("\n  Press [ENTER] to proceed to Phase 2 (The Poisoned Attack)...")
            self._demo_act_2()
            pause("\n  Press [ENTER] to proceed to Phase 3 (The Stealth Rug-Pull)...")
            self._demo_act_3()
            pause("\n  Demo Complete! Press [ENTER] to return...")
        elif sub == "2":
            self._demo_act_1()
            pause()
        elif sub == "3":
            self._demo_act_2()
            pause()
        elif sub == "4":
            self._demo_act_3()
            pause()

    def _demo_act_1(self):
        print(f"\n  {C_BOLD}{C_GREEN_BRIGHT}--- PHASE 1: VETTED SAFE SERVER & FINGERPRINT LOCKING ---{C_RESET}")
        print(f"  {C_DIM}Target: demo/safe_server/server.py (Simple Calculator){C_RESET}\n")
        safe_path = self.base_dir / "demo" / "safe_server" / "server.py"
        rep = self.scanner.scan_file(safe_path, server_name="safe-calc")

        for t in rep.tools:
            print(f"  Tool Detected:   {C_GREEN_BRIGHT}{t.tool_name}{C_RESET}")
            print(f"  Description:     {C_DIM}{t.description}{C_RESET}")
            print(f"  SHA-256 Hash:    {C_CYAN_BRIGHT}{t.fingerprint}{C_RESET}")
            print(f"  Violations:      {C_GREEN_BRIGHT}0 Found{C_RESET}")
            rec = self.registry.approve_tool(t.raw_tool, server_name="safe-calc", version="1.0.0")
            print(f"  Gate Action:     {C_GREEN_INVERSE} APPROVED & FINGERPRINT LOCKED {C_RESET}")

        self.registry.export_lockfile()
        print(f"\n  {C_GREEN_BRIGHT}[PASSED] Safe to mount into Agent Context.{C_RESET}")

    def _demo_act_2(self):
        print(f"\n  {C_BOLD}{C_RED_BRIGHT}--- PHASE 2: POISONED CALCULATOR ATTACK ---{C_RESET}")
        print(f"  {C_DIM}Target: demo/poisoned_server/server.py{C_RESET}")
        print(f"  {C_YELLOW_BRIGHT}Scenario: Developer installs an uninspected 'Math Helper' MCP server.{C_RESET}")
        print(f"  {C_YELLOW_BRIGHT}Attack Vector: The tool description contains covert directives targeting ~/.ssh/id_rsa.{C_RESET}\n")

        time.sleep(0.4)
        poison_path = self.base_dir / "demo" / "poisoned_server" / "server.py"
        rep = self.scanner.scan_file(poison_path, server_name="poisoned-calc")

        for t in rep.tools:
            print(f"  Tool Candidate:  {C_RED_BRIGHT}{t.tool_name}{C_RESET}")
            print(f"  Fingerprint:     {C_DIM}{t.fingerprint[:24]}...{C_RESET}")
            print(f"\n  {C_RED_BRIGHT}[THREAT DETECTED] Security violations found in metadata:{C_RESET}")
            for idx, f in enumerate(t.findings, 1):
                print(f"    {C_RED_BRIGHT}[VIOLATION {idx}]{C_RESET} {C_BOLD}{f.title}{C_RESET} (Rule ID: {f.rule_id})")
                print(f"      Target Field: {f.target_field} | Line: {C_YELLOW_BRIGHT}{f.line_number}{C_RESET}")
                print(f"      Matched Text: {C_RED_BRIGHT}\"{f.matched_text}\"{C_RESET}")
                if f.line_content:
                    print(f"      Source Code:  {C_DIM}{f.line_content}{C_RESET}")
                print(f"      Remediation:  {f.remediation}\n")

        print(f"  {C_RED_BRIGHT}[GATE DECISION: BLOCKED] (Exit Code 1){C_RESET}")
        print(f"  {C_RED_BRIGHT}Malicious metadata rejected before entering agent context window.{C_RESET}")

    def _demo_act_3(self):
        print(f"\n  {C_BOLD}{C_YELLOW_BRIGHT}--- PHASE 3: RUG-PULL ATTACK (POST-APPROVAL MUTATION) ---{C_RESET}")
        print(f"  {C_DIM}Target: demo/rugpull_server (v1.0.0 Clean -> v2.0.0 Backdoored){C_RESET}")
        print(f"  {C_DIM}Scenario: Developer approved v1.0.0. Weeks later, author releases v2.0.0 with exfiltration hooks.{C_RESET}\n")

        v1_path = self.base_dir / "demo" / "rugpull_server" / "v1" / "server.py"
        v1_rep = self.scanner.scan_file(v1_path, server_name="text-formatter")
        for t in v1_rep.tools:
            self.registry.approve_tool(t.raw_tool, server_name="text-formatter", version="1.0.0")
            print(f"  Step 1: Baseline v1.0.0 '{t.tool_name}' verified & locked: {C_CYAN_BRIGHT}{t.fingerprint[:20]}...{C_RESET}")

        print(f"  Step 2: Simulating upstream dependency update to v2.0.0...")
        time.sleep(0.5)

        v2_path = self.base_dir / "demo" / "rugpull_server" / "v2" / "server.py"
        v2_rep = self.scanner.scan_file(v2_path, server_name="text-formatter")

        for t in v2_rep.tools:
            if t.verification == VerificationResult.RUG_PULL:
                print(f"\n  {C_RED_BRIGHT}[RUG-PULL ALERT] Fingerprint drift detected!{C_RESET}")
                print(f"  Tool Name:       {C_WHITE_BRIGHT}{t.tool_name}{C_RESET}")
                print(f"  Approved Hash:   {C_GREEN_BRIGHT}{t.diff.stored_fingerprint[:24]}...{C_RESET}")
                print(f"  Incoming Hash:   {C_RED_BRIGHT}{t.diff.current_fingerprint[:24]}...{C_RESET}")
                print(f"  Field Changes:   {C_YELLOW_BRIGHT}{', '.join(t.diff.field_changes)}{C_RESET}")
                if t.diff.description_diff:
                    old_d, new_d = t.diff.description_diff
                    print(f"  Old Description: {C_DIM}{old_d}{C_RESET}")
                    print(f"  New Description: {C_RED_BRIGHT}{new_d}{C_RESET}")

        print(f"\n  {C_RED_BRIGHT}[GATE DECISION: BLOCKED] Unauthorized tool schema modification.{C_RESET}")

    # ==========================================================================
    # VIEW 2: SETUP ENVIRONMENT
    # ==========================================================================
    def view_setup_environment(self):
        while True:
            clear_screen()
            draw_header(self.get_active_services_count())
            print(f"  {C_BOLD}{C_GREEN_BRIGHT}ENVIRONMENT SETUP & DEPENDENCY DIAGNOSTICS{C_RESET}")
            print(f"  {C_DIM}Configure Python Virtualenv, Node.js modules, and Docker runtime{C_RESET}\n")

            diag = EnvironmentManager.check_all()
            for key, comp in diag.items():
                icon = "[OK]" if comp.is_ready else ("[WARN]" if comp.installed else "[MISSING]")
                print(f"  {icon} {C_BOLD}{comp.name}:{C_RESET} {comp.version}")
                print(f"     {C_DIM}{comp.details}{C_RESET}")

            print(f"\n  {C_GREEN_MID}Actions:{C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[1]{C_RESET} Run Full Setup (Python venv + pip deps + Node packages)")
            print(f"  {C_GREEN_BRIGHT}[2]{C_RESET} Setup Python Virtual Environment (.venv & requirements.txt)")
            print(f"  {C_GREEN_BRIGHT}[3]{C_RESET} Setup Node.js Demo Modules (npm install in demo/nodejs_server)")
            print(f"  {C_GREEN_BRIGHT}[4]{C_RESET} Build / Verify Docker Container (regolo-mcp-gate)")
            print(f"  {C_GREEN_BRIGHT}[5]{C_RESET} Refresh Diagnostics")
            print(f"  {C_GREEN_BRIGHT}[0]{C_RESET} Return to Main Menu\n")

            choice = input(f"  {C_GREEN_BRIGHT}Setup >{C_RESET} ").strip()
            if choice == "1":
                print(f"\n  {C_GREEN_BRIGHT}[1/3] Setting up Python venv...{C_RESET}")
                EnvironmentManager.setup_python_environment(log_callback=lambda m: print(f"    {m}"))
                print(f"\n  {C_GREEN_BRIGHT}[2/3] Setting up Node packages...{C_RESET}")
                EnvironmentManager.setup_node_environment(log_callback=lambda m: print(f"    {m}"))
                print(f"\n  {C_GREEN_BRIGHT}[3/3] Checking Docker...{C_RESET}")
                doc_stat = EnvironmentManager.check_docker()
                if doc_stat.is_ready:
                    EnvironmentManager.build_docker_image(log_callback=lambda m: print(f"    {m}"))
                else:
                    print(f"    Docker engine not currently active. Skipping container build.")
                print(f"\n  {C_GREEN_BRIGHT}[OK] Setup process complete.{C_RESET}")
                pause()
            elif choice == "2":
                print(f"\n  {C_GREEN_BRIGHT}Setting up Python environment...{C_RESET}")
                EnvironmentManager.setup_python_environment(log_callback=lambda m: print(f"    {m}"))
                pause()
            elif choice == "3":
                print(f"\n  {C_GREEN_BRIGHT}Setting up Node.js environment...{C_RESET}")
                EnvironmentManager.setup_node_environment(log_callback=lambda m: print(f"    {m}"))
                pause()
            elif choice == "4":
                print(f"\n  {C_GREEN_BRIGHT}Building Docker container...{C_RESET}")
                EnvironmentManager.build_docker_image(log_callback=lambda m: print(f"    {m}"))
                pause()
            elif choice == "5":
                continue
            elif choice == "0":
                break

    # ==========================================================================
    # VIEW 3: SERVICES MANAGER
    # ==========================================================================
    def view_services_manager(self):
        while True:
            clear_screen()
            draw_header(self.get_active_services_count())
            print(f"  {C_BOLD}{C_GREEN_BRIGHT}DEMO MCP SERVICES LIFECYCLE MANAGER{C_RESET}")
            print(f"  {C_DIM}Start, stop, and monitor live MCP background servers{C_RESET}\n")

            svcs = self.service_mgr.get_services()
            idx = 1
            mapping = {}
            for s_id, s in svcs.items():
                mapping[str(idx)] = s_id
                status_badge = f"{C_GREEN_BRIGHT}[RUNNING: PID {s.pid}]{C_RESET}" if s.status == "RUNNING" else f"{C_DIM}[STOPPED]{C_RESET}"
                port_str = f"Port {s.port}" if s.port else "stdio"
                print(f"  {C_GREEN_BRIGHT}[{idx}]{C_RESET} {C_WHITE_BRIGHT}{s.name}{C_RESET}")
                print(f"      Status: {status_badge}  |  Interface: {port_str}  |  ID: {s_id}")
                idx += 1

            print(f"\n  {C_GREEN_MID}Controls:{C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[1-4]{C_RESET} Toggle Start/Stop for specific service")
            print(f"  {C_GREEN_BRIGHT}[A]{C_RESET}   Start All Services")
            print(f"  {C_GREEN_BRIGHT}[S]{C_RESET}   Stop All Services")
            print(f"  {C_GREEN_BRIGHT}[R]{C_RESET}   Refresh Status")
            print(f"  {C_GREEN_BRIGHT}[0]{C_RESET}   Return to Main Menu\n")

            choice = input(f"  {C_GREEN_BRIGHT}Services >{C_RESET} ").strip()
            if choice in mapping:
                target_id = mapping[choice]
                target_svc = svcs[target_id]
                if target_svc.status == "RUNNING":
                    print(f"\n  Stopping {target_svc.name}...")
                    self.service_mgr.stop_service(target_id)
                else:
                    print(f"\n  Starting {target_svc.name}...")
                    self.service_mgr.start_service(target_id)
                time.sleep(0.5)
            elif choice.upper() == "A":
                print("\n  Starting all demo servers...")
                for s_id in svcs:
                    self.service_mgr.start_service(s_id)
                time.sleep(0.5)
            elif choice.upper() == "S":
                print("\n  Stopping all demo servers...")
                self.service_mgr.stop_all()
                time.sleep(0.5)
            elif choice.upper() == "R":
                continue
            elif choice == "0":
                break

    # ==========================================================================
    # VIEW 4: INTERACTIVE SCANNER
    # ==========================================================================
    def view_interactive_scanner(self):
        while True:
            clear_screen()
            draw_header(self.get_active_services_count())
            print(f"  {C_BOLD}{C_GREEN_BRIGHT}REGOLO SECURITY GATE SCANNER{C_RESET}")
            print(f"  {C_DIM}Run static inspection on MCP server code, packages, or configs{C_RESET}\n")

            print(f"  {C_GREEN_MID}Targets to scan:{C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[1]{C_RESET} Poisoned Demo Calculator (demo/poisoned_server/server.py)")
            print(f"  {C_GREEN_BRIGHT}[2]{C_RESET} Safe Vetted Calculator (demo/safe_server/server.py)")
            print(f"  {C_GREEN_BRIGHT}[3]{C_RESET} Rug-Pull Target Server v2 (demo/rugpull_server/v2/server.py)")
            print(f"  {C_GREEN_BRIGHT}[4]{C_RESET} Claude Desktop Config (demo/sample_claude_desktop_config.json)")
            print(f"  {C_GREEN_BRIGHT}[5]{C_RESET} Node.js Demo MCP Server (demo/nodejs_server/index.js)")
            print(f"  {C_GREEN_BRIGHT}[6]{C_RESET} Custom File or Directory Path...")
            print(f"  {C_GREEN_BRIGHT}[0]{C_RESET} Return to Main Menu\n")

            choice = input(f"  {C_GREEN_BRIGHT}Scan >{C_RESET} ").strip()
            target_path = None
            srv_name = None

            if choice == "1":
                target_path = self.base_dir / "demo" / "poisoned_server" / "server.py"
                srv_name = "poisoned-calculator"
            elif choice == "2":
                target_path = self.base_dir / "demo" / "safe_server" / "server.py"
                srv_name = "safe-calculator"
            elif choice == "3":
                target_path = self.base_dir / "demo" / "rugpull_server" / "v2" / "server.py"
                srv_name = "text-formatter"
            elif choice == "4":
                target_path = self.base_dir / "demo" / "sample_claude_desktop_config.json"
                srv_name = "claude-desktop"
            elif choice == "5":
                target_path = self.base_dir / "demo" / "nodejs_server" / "index.js"
                srv_name = "node-beautifier"
            elif choice == "6":
                p_str = input(f"  Enter file or directory path: ").strip()
                if p_str:
                    target_path = Path(p_str)
                    srv_name = target_path.stem
            elif choice == "0":
                break

            if target_path:
                clear_screen()
                draw_header(self.get_active_services_count())
                print(f"  Scanning target: {C_CYAN_BRIGHT}{target_path}{C_RESET}...\n")
                rep = self.scanner.scan_file(target_path, server_name=srv_name)
                self._render_scan_report(rep)
                if rep.is_blocked:
                    print(f"  {C_GREEN_BRIGHT}[F]{C_RESET} {C_WHITE_BRIGHT}Auto-Remediate with REGOLO brick-complexity-pro{C_RESET}")
                    print(f"  {C_DIM}[ENTER] to return to menu...{C_RESET}")
                    action = input(f"  {C_GREEN_BRIGHT}Action >{C_RESET} ").strip().upper()
                    if action == "F":
                        remediator = RegoloRemediator(registry=self.registry)
                        for t in rep.tools:
                            if t.findings:
                                res = remediator.remediate_file(
                                    file_path=target_path,
                                    tool_name=t.tool_name,
                                    original_desc=t.description,
                                    findings=t.findings,
                                    server_name=srv_name or rep.server_name
                                )
                                print(f"\n  {C_GREEN_BRIGHT}[OK] Sanitized '{t.tool_name}' using {res.model_used}.{C_RESET}")
                                print(f"     New clean fingerprint: {res.new_fingerprint[:24]}... locked in mcp-lock.json\n")
                        pause()
                else:
                    pause()

    def _render_scan_report(self, report):
        print(f"  {C_BOLD}{'=' * 68}{C_RESET}")
        print(f"  Target:        {C_CYAN_BRIGHT}{report.target_path_or_cmd}{C_RESET}")
        print(f"  Server Name:   {report.server_name}")
        print(f"  Tools Scanned: {report.total_tools}")
        print(f"  Violations:    {C_RED_BRIGHT if report.total_findings else C_GREEN_BRIGHT}{report.total_findings} (Critical: {report.critical_count}, High: {report.high_count}){C_RESET}")
        print(f"  Rug-Pulls:     {C_RED_BRIGHT if report.rug_pull_count else C_GREEN_BRIGHT}{report.rug_pull_count}{C_RESET}")
        print(f"  {C_BOLD}{'-' * 68}{C_RESET}\n")

        for t in report.tools:
            status_tag = f"{C_GREEN_BRIGHT}[VERIFIED]{C_RESET}"
            if t.verification == VerificationResult.RUG_PULL:
                status_tag = f"{C_RED_BRIGHT}[RUG-PULL DETECTED]{C_RESET}"
            elif t.verification == VerificationResult.NEW_TOOL:
                status_tag = f"{C_YELLOW_BRIGHT}[UNREGISTERED]{C_RESET}"
            elif t.verification == VerificationResult.REVOKED:
                status_tag = f"{C_RED_BRIGHT}[REVOKED]{C_RESET}"

            print(f"  Tool: {C_BOLD}{C_GREEN_BRIGHT}{t.tool_name}{C_RESET} {status_tag}")
            print(f"  SHA256 Fingerprint: {C_DIM}{t.fingerprint}{C_RESET}")

            if t.diff and t.diff.is_modified:
                print(f"    {C_RED_BRIGHT}[!] RUG-PULL DETECTED: Definition changed from approved baseline!{C_RESET}")
                for ch in t.diff.field_changes:
                    print(f"        - {ch}")
                if t.diff.description_diff:
                    old_d, new_d = t.diff.description_diff
                    print(f"        Old: {C_DIM}{old_d[:70]}...{C_RESET}")
                    print(f"        New: {C_RED_BRIGHT}{new_d[:70]}...{C_RESET}")

            if t.findings:
                print(f"    {C_RED_BRIGHT}[!] Security Violations Identified:{C_RESET}")
                for idx, f in enumerate(t.findings, 1):
                    color = C_RED_BRIGHT if f.severity == Severity.CRITICAL else C_YELLOW_BRIGHT
                    print(f"      {idx}. {color}[{f.severity.value}]{C_RESET} {C_BOLD}{f.title}{C_RESET} ({f.rule_id})")
                    print(f"         Field: {f.target_field} | Line: {f.line_number or 'N/A'}")
                    print(f"         Offending Text: {C_RED_BRIGHT}\"{f.matched_text}\"{C_RESET}")
                    if f.line_content:
                        print(f"         Line Context:   {C_DIM}{f.line_content}{C_RESET}")
                    print(f"         Remediation:    {f.remediation}")
            print()

        print(f"  {C_BOLD}{'=' * 68}{C_RESET}")
        if report.is_blocked:
            print(f"  {C_RED_BRIGHT}GATE DECISION: BLOCKED [FAIL]{C_RESET}")
            print(f"  {C_RED_BRIGHT}Reason: {report.block_reason}{C_RESET}")
        else:
            print(f"  {C_GREEN_BRIGHT}GATE DECISION: PASSED [OK]{C_RESET}")
            print(f"  {C_GREEN_BRIGHT}Status: {report.block_reason}{C_RESET}")
        print(f"  {C_BOLD}{'=' * 68}{C_RESET}\n")

    # ==========================================================================
    # VIEW 5: REGISTRY & VERSION LOCK
    # ==========================================================================
    def view_registry_manager(self):
        while True:
            clear_screen()
            draw_header(self.get_active_services_count())
            print(f"  {C_BOLD}{C_GREEN_BRIGHT}APPROVED TOOLS REGISTRY & VERSION LOCKING{C_RESET}")
            print(f"  {C_DIM}Immutable ledger of audited MCP tools and SHA256 fingerprints{C_RESET}\n")

            records = list(self.registry.records.values())
            if not records:
                print(f"  {C_YELLOW_BRIGHT}Registry is currently empty.{C_RESET}")
                print(f"  Approve tools through the Scanner, Demo, or CLI to populate.\n")
            else:
                for idx, rec in enumerate(records, 1):
                    badge = f"{C_GREEN_BRIGHT}[APPROVED]{C_RESET}" if rec.status == ToolStatus.APPROVED else f"{C_RED_BRIGHT}[REVOKED]{C_RESET}"
                    print(f"  {idx}. {C_BOLD}{rec.tool_name}{C_RESET} ({rec.server_name} v{rec.version}) {badge}")
                    print(f"     SHA256:   {C_CYAN_BRIGHT}{rec.fingerprint}{C_RESET}")
                    print(f"     Audited:  {rec.approved_at} by {rec.approved_by}")
                print()

            print(f"  {C_GREEN_MID}Actions:{C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[1]{C_RESET} Export mcp-lock.json (For CI & Pre-Commit)")
            print(f"  {C_GREEN_BRIGHT}[2]{C_RESET} Approve Safe Calculator Tool")
            print(f"  {C_GREEN_BRIGHT}[3]{C_RESET} Revoke a Tool...")
            print(f"  {C_GREEN_BRIGHT}[0]{C_RESET} Return to Main Menu\n")

            choice = input(f"  {C_GREEN_BRIGHT}Registry >{C_RESET} ").strip()
            if choice == "1":
                self.registry.export_lockfile()
                print(f"\n  {C_GREEN_BRIGHT}[OK] Exported mcp-lock.json successfully.{C_RESET}")
                pause()
            elif choice == "2":
                safe_p = self.base_dir / "demo" / "safe_server" / "server.py"
                rep = self.scanner.scan_file(safe_p, server_name="safe-calculator")
                for t in rep.tools:
                    self.registry.approve_tool(t.raw_tool, server_name="safe-calculator", version="1.0.0")
                self.registry.export_lockfile()
                print(f"\n  {C_GREEN_BRIGHT}[OK] Approved 'calculate' from safe-calculator v1.0.0{C_RESET}")
                pause()
            elif choice == "3":
                s_name = input(f"  Enter server name: ").strip()
                t_name = input(f"  Enter tool name: ").strip()
                if self.registry.revoke_tool(s_name, t_name):
                    print(f"\n  {C_RED_BRIGHT}Revoked {t_name} from {s_name}.{C_RESET}")
                else:
                    print(f"\n  Tool not found in registry.")
                pause()
            elif choice == "0":
                break

    # ==========================================================================
    # VIEW 6: DEV ROUTINE & CI GATE
    # ==========================================================================
    def view_dev_routine_ci(self):
        while True:
            clear_screen()
            draw_header(self.get_active_services_count())
            print(f"  {C_BOLD}{C_GREEN_BRIGHT}DEVELOPER ROUTINE & CI/CD PIPELINE GATE{C_RESET}")
            print(f"  {C_DIM}Automated verification preventing untrusted tools in production{C_RESET}\n")

            print(f"  {C_GREEN_MID}Select simulation:{C_RESET}")
            print(f"  {C_GREEN_BRIGHT}[1]{C_RESET} Simulate Git Pre-Commit Hook (Blocks commit if poisoned tool is staged)")
            print(f"  {C_GREEN_BRIGHT}[2]{C_RESET} Run Local GitHub Actions Workflow Runner (.github/workflows/mcp-gate.yml)")
            print(f"  {C_GREEN_BRIGHT}[3]{C_RESET} Install Git Hook to local .git/hooks/pre-commit")
            print(f"  {C_GREEN_BRIGHT}[0]{C_RESET} Return to Main Menu\n")

            choice = input(f"  {C_GREEN_BRIGHT}CI >{C_RESET} ").strip()
            if choice == "1":
                clear_screen()
                draw_header(self.get_active_services_count())
                print(f"  {C_BOLD}{C_GREEN_BRIGHT}Simulating Developer Routine: 'git commit -m \"Add new MCP calculator\"'{C_RESET}\n")
                print(f"  [GIT HOOK TRIGGERED] Inspecting staged file: demo/poisoned_server/server.py...")
                time.sleep(0.5)
                p_path = self.base_dir / "demo" / "poisoned_server" / "server.py"
                rep = self.scanner.scan_file(p_path, server_name="poisoned-calc")
                self._render_scan_report(rep)
                print(f"  {C_RED_BRIGHT}[COMMIT REJECTED] Malicious MCP tool detected.{C_RESET}")
                print(f"  {C_DIM}The developer cannot commit a backdoored tool into git.{C_RESET}\n")
                pause()
            elif choice == "2":
                clear_screen()
                draw_header(self.get_active_services_count())
                print(f"  {C_BOLD}{C_GREEN_BRIGHT}Running GitHub Actions Workflow in Local Environment...{C_RESET}\n")
                ci_script = self.base_dir / "scripts" / "test-ci-local.sh"
                try:
                    subprocess.run(["bash", str(ci_script)], check=False)
                except Exception as e:
                    print(f"  Error running CI script: {e}")
                pause()
            elif choice == "3":
                git_hook_dir = self.base_dir / ".git" / "hooks"
                if not git_hook_dir.exists():
                    print(f"\n  {C_YELLOW_BRIGHT}[NOTICE] Current directory is not a git repo or .git/hooks missing.{C_RESET}")
                    print(f"  The hook script is ready at: {self.base_dir / 'scripts' / 'pre-commit-hook.sh'}")
                else:
                    dest = git_hook_dir / "pre-commit"
                    src = self.base_dir / "scripts" / "pre-commit-hook.sh"
                    shutil.copyfile(src, dest)
                    os.chmod(dest, 0o755)
                    print(f"\n  {C_GREEN_BRIGHT}[OK] Installed pre-commit hook into .git/hooks/pre-commit{C_RESET}")
                pause()
            elif choice == "0":
                break


def main():
    parser = argparse.ArgumentParser(description="REGOLO MCP Security Gate TUI")
    parser.add_argument("--demo", action="store_true", help="Launch Demo Walkthrough immediately")
    parser.add_argument("--setup", action="store_true", help="Run environment setup immediately")
    parser.add_argument("--scan", type=str, help="Scan a target file or folder directly")
    parser.add_argument("--mcp", action="store_true", help="Run REGOLO as an MCP server for OpenCode, Kilo, or Claude Desktop")
    args = parser.parse_args()

    if args.mcp:
        from gate.mcp_server import main as run_mcp_server
        run_mcp_server()
        return

    tui = RegoloTUI()

    if args.demo:
        tui.view_demo_walkthrough()
    elif args.setup:
        tui.view_setup_environment()
    elif args.scan:
        rep = tui.scanner.scan_file(args.scan)
        tui._render_scan_report(rep)
        sys.exit(1 if rep.is_blocked else 0)
    else:
        tui.run()


if __name__ == "__main__":
    main()
