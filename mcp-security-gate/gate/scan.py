"""
REGOLO MCP Security Gate - Core Scanner Engine
Inspects MCP servers, configs, and tool definitions for injection vectors,
sensitive exfiltration, and unauthorized rug-pull alterations.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from .fingerprint import FingerprintDiff, ToolFingerprint
from .registry import ApprovedRecord, Registry, ToolStatus, VerificationResult
from .rules import Finding, RuleEngine, Severity


@dataclass
class ToolScanReport:
    tool_name: str
    description: str
    fingerprint: str
    findings: List[Finding] = field(default_factory=list)
    verification: VerificationResult = VerificationResult.NEW_TOOL
    diff: Optional[FingerprintDiff] = None
    registry_record: Optional[ApprovedRecord] = None
    raw_tool: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_threats(self) -> bool:
        return len(self.findings) > 0 or self.verification in (VerificationResult.RUG_PULL, VerificationResult.REVOKED)

    @property
    def max_severity(self) -> Optional[Severity]:
        if not self.findings:
            if self.verification == VerificationResult.RUG_PULL:
                return Severity.CRITICAL
            if self.verification == VerificationResult.REVOKED:
                return Severity.HIGH
            return None
        severities = [f.severity for f in self.findings]
        if Severity.CRITICAL in severities or self.verification == VerificationResult.RUG_PULL:
            return Severity.CRITICAL
        if Severity.HIGH in severities or self.verification == VerificationResult.REVOKED:
            return Severity.HIGH
        if Severity.MEDIUM in severities:
            return Severity.MEDIUM
        return Severity.LOW


@dataclass
class GateScanReport:
    server_name: str
    target_path_or_cmd: str
    tools: List[ToolScanReport] = field(default_factory=list)
    is_blocked: bool = False
    block_reason: str = ""

    @property
    def total_tools(self) -> int:
        return len(self.tools)

    @property
    def total_findings(self) -> int:
        return sum(len(t.findings) for t in self.tools)

    @property
    def critical_count(self) -> int:
        rug_pull_count = sum(1 for t in self.tools if t.verification == VerificationResult.RUG_PULL)
        rule_crit = sum(sum(1 for f in t.findings if f.severity == Severity.CRITICAL) for t in self.tools)
        return rule_crit + rug_pull_count

    @property
    def high_count(self) -> int:
        return sum(sum(1 for f in t.findings if f.severity == Severity.HIGH) for t in self.tools)

    @property
    def rug_pull_count(self) -> int:
        return sum(1 for t in self.tools if t.verification == VerificationResult.RUG_PULL)


class GateScanner:
    """Orchestrates security scanning of MCP tool definitions across sources."""

    def __init__(self, registry: Optional[Registry] = None):
        self.registry = registry or Registry()

    def scan_tool_dict(
        self,
        tool: Dict[str, Any],
        server_name: str = "default",
    ) -> ToolScanReport:
        """Analyzes a single tool schema dictionary."""
        name = tool.get("name", "unnamed")
        desc = tool.get("description", "")
        fp = ToolFingerprint.compute_hash(tool)

        # 1. Static security rules check
        findings = RuleEngine.inspect_tool(tool)

        # 2. Registry verification
        ver_result, diff, record = self.registry.verify_tool(tool, server_name=server_name)

        return ToolScanReport(
            tool_name=name,
            description=desc,
            fingerprint=fp,
            findings=findings,
            verification=ver_result,
            diff=diff,
            registry_record=record,
            raw_tool=tool,
        )

    def scan_tools(
        self,
        tools: List[Dict[str, Any]],
        server_name: str = "default",
        source_label: str = "memory",
    ) -> GateScanReport:
        """Analyzes a list of tool schema dictionaries."""
        report = GateScanReport(
            server_name=server_name,
            target_path_or_cmd=source_label,
            tools=[],
        )

        for tool in tools:
            tool_rep = self.scan_tool_dict(tool, server_name=server_name)
            report.tools.append(tool_rep)

        # Evaluate gating verdict
        if report.critical_count > 0:
            report.is_blocked = True
            report.block_reason = f"CRITICAL SECURITY THREAT: Found {report.critical_count} critical rule violations / rug-pulls."
        elif report.high_count > 0:
            report.is_blocked = True
            report.block_reason = f"HIGH RISK: Found {report.high_count} high-severity security findings."
        else:
            report.is_blocked = False
            report.block_reason = "PASS: No injection patterns or rug pulls detected."

        return report

    def scan_file(self, file_path: Union[str, Path], server_name: Optional[str] = None) -> GateScanReport:
        """Extracts and scans tool schemas from a JSON, Python, or JavaScript/TypeScript file."""
        path = Path(file_path).resolve()
        if not path.exists():
            rep = GateScanReport(server_name=server_name or path.name, target_path_or_cmd=str(path))
            rep.is_blocked = True
            rep.block_reason = f"Target file does not exist: {path}"
            return rep

        srv_name = server_name or path.stem

        # Try parsing as raw JSON
        if path.suffix in (".json",):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tools: List[Dict[str, Any]] = []
                    if isinstance(data, list):
                        tools = data
                    elif isinstance(data, dict):
                        if "tools" in data and isinstance(data["tools"], list):
                            tools = data["tools"]
                        elif "mcpServers" in data:
                            # Claude config format
                            return self.scan_claude_config(path)
                        else:
                            tools = [data]
                    return self.scan_tools(tools, server_name=srv_name, source_label=str(path))
            except Exception as e:
                pass

        # Try running stdio handshake first if runtime exists
        if path.suffix == ".py" and shutil.which(sys.executable):
            stdio_rep = self.scan_stdio_mcp_server([sys.executable, str(path)], server_name=srv_name, timeout=4)
            if stdio_rep.total_tools > 0 and stdio_rep.tools[0].tool_name != path.stem:
                return stdio_rep

        if path.suffix in (".js", ".mjs") and shutil.which("node"):
            stdio_rep = self.scan_stdio_mcp_server(["node", str(path)], server_name=srv_name, timeout=4)
            if stdio_rep.total_tools > 0 and stdio_rep.tools[0].tool_name != path.stem:
                return stdio_rep

        # Static extraction from Python / JS code
        extracted_tools = self._extract_tools_from_source(path)
        return self.scan_tools(extracted_tools, server_name=srv_name, source_label=str(path))

    def scan_stdio_mcp_server(
        self,
        command: List[str],
        server_name: str = "stdio-server",
        timeout: int = 8,
    ) -> GateScanReport:
        """
        Launches an MCP server over stdio, performs JSON-RPC handshake,
        calls tools/list, and scans the live returned tool schemas.
        """
        req_init = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "regolo-security-gate", "version": "1.0.0"}
            }
        }) + "\n"

        req_list = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }) + "\n"

        try:
            proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # Send initialize and tools/list
            input_data = req_init + req_list
            stdout, stderr = proc.communicate(input=input_data, timeout=timeout)
            
            # Parse responses
            tools: List[Dict[str, Any]] = []
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    if payload.get("id") == 2 and "result" in payload:
                        tools = payload["result"].get("tools", [])
                        break
                except json.JSONDecodeError:
                    continue

            if not tools:
                # Fallback to static extraction from script path if stdio didn't yield tools
                for arg in command:
                    p = Path(arg)
                    if p.exists() and p.is_file():
                        extracted = self._extract_tools_from_source(p)
                        if extracted:
                            return self.scan_tools(extracted, server_name=server_name, source_label=str(arg))

            return self.scan_tools(tools, server_name=server_name, source_label=" ".join(command))

        except Exception as e:
            # Fallback to static extraction if command execution failed (e.g. node not installed)
            for arg in command:
                p = Path(arg)
                if p.exists() and p.is_file():
                    extracted = self._extract_tools_from_source(p)
                    if extracted:
                        return self.scan_tools(extracted, server_name=server_name, source_label=str(arg))

            rep = GateScanReport(server_name=server_name, target_path_or_cmd=" ".join(command))
            rep.is_blocked = True
            rep.block_reason = f"Failed to execute stdio MCP server: {e}"
            return rep

    def scan_claude_config(self, config_path: Path) -> GateScanReport:
        """Inspects all servers defined in a claude_desktop_config.json."""
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        servers = data.get("mcpServers", {})
        combined_tools: List[Dict[str, Any]] = []

        base_dir = config_path.parent

        for name, conf in servers.items():
            args = conf.get("args", [])
            for arg in args:
                p = Path(arg)
                if not p.is_absolute():
                    candidate1 = (base_dir / p).resolve()
                    candidate2 = (Path.cwd() / p).resolve()
                    candidate3 = (base_dir.parent / p).resolve()
                    if candidate1.exists():
                        p = candidate1
                    elif candidate2.exists():
                        p = candidate2
                    elif candidate3.exists():
                        p = candidate3
                if p.exists() and p.is_file():
                    sub_rep = self.scan_file(p, server_name=name)
                    for t in sub_rep.tools:
                        combined_tools.append(t.raw_tool)

        return self.scan_tools(combined_tools, server_name="claude-config", source_label=str(config_path))

    def _extract_tools_from_source(self, path: Path) -> List[Dict[str, Any]]:
        """Static pattern extractor for Python (@mcp.tool, FastMCP) and JS/TS tool definitions."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        tools: List[Dict[str, Any]] = []

        # 1. Match Python docstring tools: def tool_name(...):\n    """Description..."""
        py_tool_pattern = re.compile(
            r"@(?:mcp|server|app)\.tool\s*\([^)]*\)\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\([^)]*\)[^:]*:\s*(?:\"\"\"([\s\S]*?)\"\"\"|'''([\s\S]*?)''')",
            re.MULTILINE
        )
        for match in py_tool_pattern.finditer(content):
            name = match.group(1)
            desc = match.group(2) or match.group(3) or ""
            tools.append({
                "name": name,
                "description": desc.strip(),
                "inputSchema": {"type": "object", "properties": {}},
            })

        # 2. Match JS/TS server.tool("name", "description", { ... })
        js_tool_pattern = re.compile(
            r"(?:server|mcp)\.tool\s*\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"']([^\"']+)[\"']",
            re.MULTILINE
        )
        for match in js_tool_pattern.finditer(content):
            name = match.group(1)
            desc = match.group(2)
            tools.append({
                "name": name,
                "description": desc.strip(),
                "inputSchema": {"type": "object", "properties": {}},
            })

        # 3. Match JS/TS object registration: name: "...", description: "..."
        if not tools:
            js_obj_pattern = re.compile(
                r"name\s*:\s*[\"']([a-zA-Z0-9_-]+)[\"']\s*,\s*description\s*:\s*[\"`']([\s\S]*?)[\"`']\s*,",
                re.MULTILINE
            )
            for match in js_obj_pattern.finditer(content):
                name = match.group(1)
                desc = match.group(2)
                tools.append({
                    "name": name,
                    "description": desc.strip(),
                    "inputSchema": {"type": "object", "properties": {}},
                })

        # If nothing matched, treat the whole file as a potential description payload for defense-in-depth
        if not tools and path.suffix in (".py", ".js", ".ts", ".json"):
            tools.append({
                "name": path.stem,
                "description": content[:2000],
                "inputSchema": {"type": "object", "properties": {}},
            })

        return tools
