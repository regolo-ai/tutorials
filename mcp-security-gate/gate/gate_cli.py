"""
REGOLO MCP Security Gate - CLI Interface
Runs gate checks in terminal, pre-commit hooks, and CI/CD pipelines.
"""

import argparse
import json
import sys
from pathlib import Path

from .fingerprint import ToolFingerprint
from .registry import Registry, VerificationResult
from .remediate import RegoloRemediator
from .rules import Severity
from .scan import GateScanner


def format_green(text: str) -> str:
    return f"\033[38;5;46m{text}\033[0m"


def format_red(text: str) -> str:
    return f"\033[38;5;196m{text}\033[0m"


def format_yellow(text: str) -> str:
    return f"\033[38;5;226m{text}\033[0m"


def format_dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


def print_report(report) -> None:
    print("\n" + "=" * 70)
    print(format_green(" [REGOLO] MCP SECURITY GATE SCAN REPORT "))
    print("=" * 70)
    print(f"Target:        {report.target_path_or_cmd}")
    print(f"Server Name:   {report.server_name}")
    print(f"Tools Scanned: {report.total_tools}")
    print(f"Violations:    {report.total_findings} (Critical: {report.critical_count}, High: {report.high_count})")
    print(f"Rug-Pulls:     {report.rug_pull_count}")
    print("-" * 70)

    for tool in report.tools:
        status_tag = format_green("[VERIFIED]")
        if tool.verification == VerificationResult.RUG_PULL:
            status_tag = format_red("[RUG-PULL DETECTED]")
        elif tool.verification == VerificationResult.REVOKED:
            status_tag = format_red("[REVOKED]")
        elif tool.verification == VerificationResult.NEW_TOOL:
            status_tag = format_yellow("[UNREGISTERED]")

        print(f"\nTool: {format_green(tool.tool_name)} {status_tag}")
        print(f"SHA256 Fingerprint: {format_dim(tool.fingerprint[:24] + '...')}")

        if tool.diff and tool.diff.is_modified:
            print(format_red("  [!] RUG-PULL ALERT: Definition modified after approval!"))
            for ch in tool.diff.field_changes:
                print(format_red(f"      - {ch}"))
            if tool.diff.description_diff:
                old_d, new_d = tool.diff.description_diff
                print(format_dim(f"      Old: {old_d[:60]}..."))
                print(format_red(f"      New: {new_d[:60]}..."))

        if tool.findings:
            print(format_red(f"  [!] Found {len(tool.findings)} Security Violations:"))
            for idx, f in enumerate(tool.findings, 1):
                sev_color = format_red if f.severity == Severity.CRITICAL else format_yellow
                print(f"    {idx}. {sev_color('[' + f.severity.value + ']')} {f.rule_id}: {f.title}")
                print(f"       Field: {f.target_field} | Line: {f.line_number or 'N/A'}")
                print(f"       Offending: {format_red(f.matched_text)}")
                if f.line_content:
                    print(f"       Source Line {f.line_number}: {format_dim(f.line_content)}")
                print(f"       Remediation: {f.remediation}")

    print("\n" + "=" * 70)
    if report.is_blocked:
        print(format_red(f" GATE DECISION: BLOCKED"))
        print(format_red(f" Reason: {report.block_reason}"))
        print("=" * 70 + "\n")
        sys.exit(1)
    else:
        print(format_green(" GATE DECISION: PASSED"))
        print(format_green(f" Status: {report.block_reason}"))
        print("=" * 70 + "\n")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="REGOLO MCP Security Gate CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan a file, folder, or MCP server")
    scan_parser.add_argument("target", help="File path, JSON schema, or script to inspect")
    scan_parser.add_argument("--server-name", default=None, help="Identifier name for server")
    scan_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    scan_parser.add_argument("--remediate", action="store_true", help="Auto-remediate vulnerabilities using REGOLO brick-complexity-pro")
    scan_parser.add_argument("--create-pr", action="store_true", help="Open a GitHub Pull Request with the sanitized tool definitions")

    # remediate command
    remed_parser = subparsers.add_parser("remediate", help="Sanitize a poisoned MCP tool using brick-complexity-pro")
    remed_parser.add_argument("target", help="File path to sanitize")
    remed_parser.add_argument("--server-name", default="default", help="Server name")
    remed_parser.add_argument("--create-pr", action="store_true", help="Open a Pull Request with the sanitized code")

    # approve command
    approve_parser = subparsers.add_parser("approve", help="Approve and fingerprint a verified tool")
    approve_parser.add_argument("target", help="File path containing verified tool")
    approve_parser.add_argument("--server-name", default="default", help="Server name")
    approve_parser.add_argument("--version", default="1.0.0", help="Tool version")

    # lock command
    lock_parser = subparsers.add_parser("lock", help="Export mcp-lock.json from registry")
    lock_parser.add_argument("--out", default="mcp-lock.json", help="Path to lockfile")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    registry = Registry()
    scanner = GateScanner(registry)

    if args.command == "scan":
        report = scanner.scan_file(args.target, server_name=args.server_name)
        
        if getattr(args, "remediate", False) and report.is_blocked:
            print_report(report)
            print(format_yellow("\n[REGOLO AI] Initiating Automated Remediation with brick-complexity-pro..."))
            remediator = RegoloRemediator(registry=registry)
            target_p = Path(args.target)
            for t in report.tools:
                if t.findings:
                    res = remediator.remediate_file(
                        file_path=target_p,
                        tool_name=t.tool_name,
                        original_desc=t.description,
                        findings=t.findings,
                        server_name=args.server_name or report.server_name,
                    )
                    if res.success:
                        print(format_green(f"  [OK] Sanitized '{t.tool_name}' using {res.model_used}."))
                        print(format_dim(f"     New description: {res.sanitized_description}"))
                        print(format_green(f"     Updated fingerprint: {res.new_fingerprint[:24]}... in mcp-lock.json"))
                    else:
                        print(format_red(f"  [FAILED] Failed to sanitize {t.tool_name}."))

            if getattr(args, "create_pr", False):
                pr_res = remediator.create_remediation_pull_request()
                print(format_green(f"  [PR] Remediation PR: {pr_res}"))
            sys.exit(0)

        if args.json:
            out = {
                "server_name": report.server_name,
                "target": report.target_path_or_cmd,
                "is_blocked": report.is_blocked,
                "block_reason": report.block_reason,
                "total_findings": report.total_findings,
                "critical_count": report.critical_count,
                "high_count": report.high_count,
                "rug_pull_count": report.rug_pull_count,
                "tools": [
                    {
                        "name": t.tool_name,
                        "fingerprint": t.fingerprint,
                        "verification": t.verification.value,
                        "findings": [
                            {
                                "rule_id": f.rule_id,
                                "severity": f.severity.value,
                                "title": f.title,
                                "line": f.line_number,
                                "matched": f.matched_text,
                            }
                            for f in t.findings
                        ],
                    }
                    for t in report.tools
                ],
            }
            print(json.dumps(out, indent=2))
            sys.exit(1 if report.is_blocked else 0)
        else:
            print_report(report)

    elif args.command == "remediate":
        report = scanner.scan_file(args.target, server_name=args.server_name)
        remediator = RegoloRemediator(registry=registry)
        target_p = Path(args.target)
        for t in report.tools:
            res = remediator.remediate_file(
                file_path=target_p,
                tool_name=t.tool_name,
                original_desc=t.description,
                findings=t.findings,
                server_name=args.server_name or report.server_name,
            )
            print(format_green(f"Sanitized '{t.tool_name}' with {res.model_used}. Clean hash: {res.new_fingerprint[:16]}..."))
        if args.create_pr:
            pr_res = remediator.create_remediation_pull_request()
            print(format_green(f"Pull Request status: {pr_res}"))

    elif args.command == "approve":
        report = scanner.scan_file(args.target, server_name=args.server_name)
        if report.critical_count > 0 or report.high_count > 0:
            print(format_red(f"Cannot approve tool with critical/high security findings!"))
            sys.exit(1)
        
        for t in report.tools:
            rec = registry.approve_tool(t.raw_tool, server_name=args.server_name or report.server_name, version=args.version)
            print(format_green(f"Approved '{rec.tool_name}' ({rec.fingerprint[:16]}...) in server '{rec.server_name}' v{rec.version}"))
        registry.export_lockfile()
        print(format_green("Exported updated mcp-lock.json"))

    elif args.command == "lock":
        registry.export_lockfile(Path(args.out))
        print(format_green(f"Exported mcp-lock.json with {len(registry.records)} tools."))


if __name__ == "__main__":
    main()
