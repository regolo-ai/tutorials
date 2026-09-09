#!/usr/bin/env python3
"""
REGOLO MCP Security Gate - MCP Server Interface
Exposes the REGOLO security gate as an MCP server itself, so AI agents like
OpenCode, Kilo, or Claude Desktop can use REGOLO tools to inspect and audit other tools.
"""

import json
from pathlib import Path
import sys

from gate.registry import Registry, VerificationResult
from gate.remediate import RegoloRemediator
from gate.rules import RuleEngine, Severity
from gate.scan import GateScanner


def handle_initialize(msg_id):
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "regolo-security-gate",
                "version": "1.0.0"
            }
        }
    }


def handle_tools_list(msg_id):
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "tools": [
                {
                    "name": "security_gate_scan_tool",
                    "description": "Inspect an MCP tool's name, description, and input schema for prompt injection, hidden directives, zero-width payloads, and credential exfiltration targets.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "tool_name": {
                                "type": "string",
                                "description": "The name of the tool to inspect."
                            },
                            "description": {
                                "type": "string",
                                "description": "The full description string of the tool."
                            },
                            "schema_properties": {
                                "type": "object",
                                "description": "Optional dictionary of parameter descriptions."
                            }
                        },
                        "required": ["tool_name", "description"]
                    }
                },
                {
                    "name": "security_gate_audit_file",
                    "description": "Scans a local file, MCP script, or agent configuration file (e.g. opencode.json, claude_desktop_config.json) for malicious tool definitions.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute or relative path to the file to audit."
                            }
                        },
                        "required": ["file_path"]
                    }
                },
                {
                    "name": "security_gate_check_rugpull",
                    "description": "Compares an incoming tool schema against the locked approved registry (mcp-lock.json) to detect post-approval modifications.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "server_name": {
                                "type": "string",
                                "description": "Server identifier."
                            },
                            "tool_name": {
                                "type": "string",
                                "description": "Tool name."
                            },
                            "description": {
                                "type": "string",
                                "description": "Incoming description."
                            }
                        },
                        "required": ["server_name", "tool_name", "description"]
                    }
                },
                {
                    "name": "security_gate_remediate_tool",
                    "description": "Sanitizes a poisoned MCP tool definition using REGOLO's brick-complexity-pro reasoning model, purging injections and updating mcp-lock.json.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the MCP server script to sanitize."
                            },
                            "tool_name": {
                                "type": "string",
                                "description": "Name of the tool to clean."
                            },
                            "server_name": {
                                "type": "string",
                                "description": "Optional server name for the registry."
                            }
                        },
                        "required": ["file_path", "tool_name"]
                    }
                }
            ]
        }
    }


def handle_tool_call(msg_id, params):
    name = params.get("name")
    args = params.get("arguments", {})

    registry = Registry()
    scanner = GateScanner(registry)

    if name in ("security_gate_scan_tool", "regolo_scan_tool"):
        tool_dict = {
            "name": args.get("tool_name", "unnamed"),
            "description": args.get("description", ""),
            "inputSchema": {"type": "object", "properties": args.get("schema_properties", {})}
        }
        report = scanner.scan_tool_dict(tool_dict)
        findings_summary = [
            f"[{f.severity.value}] {f.title} (Line {f.line_number}): '{f.matched_text}' -> Remediation: {f.remediation}"
            for f in report.findings
        ]
        decision = "BLOCKED" if report.has_threats else "PASSED"
        output = {
            "decision": decision,
            "threats_found": len(report.findings),
            "fingerprint": report.fingerprint,
            "violations": findings_summary
        }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(output, indent=2)}]
            }
        }

    elif name in ("security_gate_audit_file", "regolo_audit_file"):
        path_str = args.get("file_path", "")
        rep = scanner.scan_file(Path(path_str))
        res_data = {
            "file": str(rep.target_path_or_cmd),
            "is_blocked": rep.is_blocked,
            "verdict": "BLOCKED" if rep.is_blocked else "PASSED",
            "reason": rep.block_reason,
            "tools_scanned": rep.total_tools,
            "violations_count": rep.total_findings,
            "rug_pulls": rep.rug_pull_count
        }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(res_data, indent=2)}]
            }
        }

    elif name in ("security_gate_check_rugpull", "regolo_check_rugpull"):
        tool_dict = {
            "name": args.get("tool_name"),
            "description": args.get("description"),
            "inputSchema": {}
        }
        ver_res, diff, rec = registry.verify_tool(tool_dict, server_name=args.get("server_name", "default"))
        is_rugpull = ver_res == VerificationResult.RUG_PULL
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "status": ver_res.value,
                        "is_rugpull": is_rugpull,
                        "changes": diff.field_changes if diff else []
                    }, indent=2)
                }]
            }
        }

    elif name in ("security_gate_remediate_tool", "regolo_remediate_tool"):
        file_p = Path(args.get("file_path", ""))
        tool_n = args.get("tool_name", "")
        srv_n = args.get("server_name", "default")
        rep = scanner.scan_file(file_p, server_name=srv_n)
        
        target_tool = None
        for t in rep.tools:
            if t.tool_name == tool_n or len(rep.tools) == 1:
                target_tool = t
                break

        if not target_tool:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": f"Tool '{tool_n}' not found in {file_p}"}
            }

        remediator = RegoloRemediator(registry=registry)
        res = remediator.remediate_file(
            file_path=file_p,
            tool_name=target_tool.tool_name,
            original_desc=target_tool.description,
            findings=target_tool.findings,
            server_name=srv_n,
        )
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": res.success,
                        "tool_name": res.tool_name,
                        "sanitized_description": res.sanitized_description,
                        "model_used": res.model_used,
                        "new_fingerprint": res.new_fingerprint,
                        "status": "APPROVED & LOCKED in mcp-lock.json"
                    }, indent=2)
                }]
            }
        }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": "Method not found"}
    }


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            msg_id = req.get("id")

            if method == "initialize":
                resp = handle_initialize(msg_id)
            elif method == "tools/list":
                resp = handle_tools_list(msg_id)
            elif method == "tools/call":
                resp = handle_tool_call(msg_id, req.get("params", {}))
            else:
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
