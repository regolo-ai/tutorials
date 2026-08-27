"""Plugins Bridge for Claude Code, OpenClaw, and Model Context Protocol (MCP).
Enables seamless integration of Cognee Long-Term Memory directly into developer CLI agents.
"""

import json
from pathlib import Path
from typing import Any, Dict

import config


class PluginsBridgeManager:
    """Manages configuration and script generation for Claude Code and OpenClaw."""

    def __init__(self, output_dir: Path = config.PLUGINS_CONFIG_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def generate_claude_code_config(self) -> Path:
        """Generate .mcp.json and CLAUDE.md instructions for Claude Code."""
        mcp_config = {
            "mcpServers": {
                "regolo-cognee-memory": {
                    "command": "python3",
                    "args": [str(self.output_dir / "mcp_server.py")],
                    "env": {
                        "REGOLO_API_KEY": config.REGOLO_API_KEY,
                        "REGOLO_BASE_URL": config.REGOLO_BASE_URL,
                        "COGNEE_API_URL": config.COGNEE_API_URL,
                    },
                }
            }
        }

        mcp_file = self.output_dir / "claude_code_mcp.json"
        with open(mcp_file, "w", encoding="utf-8") as f:
            json.dump(mcp_config, f, indent=2)

        # Generate sample CLAUDE.md memory guidance
        claude_md_content = (
            "# Regolo + Cognee Long-Term Memory Protocol\n\n"
            "This repository uses **Cognee Knowledge Graph Memory** on **Regolo.ai**.\n\n"
            "## Memory Guidelines for Claude Code:\n"
            "1. Before modifying core modules, execute `cognee_recall` with your task intent.\n"
            "2. Always follow linked `ArchitecturalDecision` (ADR) nodes.\n"
            "3. Check for previous `PastCIError` nodes to avoid repeating solved bugs.\n"
            "4. After completing a critical PR or security fix, call `cognee_record_pr`.\n"
        )
        claude_md_file = self.output_dir / "CLAUDE.md"
        with open(claude_md_file, "w", encoding="utf-8") as f:
            f.write(claude_md_content)

        return mcp_file

    def generate_openclaw_config(self) -> Path:
        """Generate OpenClaw adapter configuration."""
        openclaw_config = {
            "name": "openclaw-cognee-memory-plugin",
            "version": "1.0.0",
            "provider": "Regolo.ai EU Sovereign Cloud",
            "hooks": {
                "on_session_start": "recall_repository_context",
                "on_pre_tool_use": "validate_adr_compliance",
                "on_post_pr_merge": "record_memory_node",
            },
            "endpoint": config.COGNEE_API_URL,
            "router": config.MODEL_BRICK_ROUTER,
            "models": {
                "router": config.MODEL_BRICK_ROUTER,
                "extraction": config.MODEL_COGNEE_EXTRACT,
                "reasoning": config.MODEL_AGENT_REASONING,
                "coding": config.MODEL_AGENT_CODER,
            },
        }

        openclaw_file = self.output_dir / "openclaw_plugin.json"
        with open(openclaw_file, "w", encoding="utf-8") as f:
            json.dump(openclaw_config, f, indent=2)

        return openclaw_file

    def generate_python_mcp_server(self) -> Path:
        """Write lightweight stdio MCP server for agent integration."""
        server_code = (
            '#!/usr/bin/env python3\n'
            '"""Regolo.ai + Cognee MCP Memory Server for Claude Code & OpenClaw."""\n'
            'import json\n'
            'import sys\n'
            'from pathlib import Path\n\n'
            '# Add parent directory to path\n'
            'sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n'
            'from core.cognee_engine import CogneeMemoryEngine\n\n'
            'engine = CogneeMemoryEngine()\n\n'
            'def handle_request(line: str):\n'
            '    try:\n'
            '        req = json.loads(line)\n'
            '        method = req.get("method")\n'
            '        params = req.get("params", {})\n'
            '        req_id = req.get("id")\n\n'
            '        if method == "tools/list":\n'
            '            tools = [\n'
            '                {\n'
            '                    "name": "cognee_recall",\n'
            '                    "description": "Recall ADRs, past CI fixes, and conventions from Cognee memory graph.",\n'
            '                    "inputSchema": {\n'
            '                        "type": "object",\n'
            '                        "properties": {"query": {"type": "string"}},\n'
            '                        "required": ["query"],\n'
            '                    },\n'
            '                },\n'
            '                {\n'
            '                    "name": "cognee_cognify",\n'
            '                    "description": "Index directory or codebase into Cognee memory graph.",\n'
            '                    "inputSchema": {\n'
            '                        "type": "object",\n'
            '                        "properties": {"path": {"type": "string"}},\n'
            '                        "required": ["path"],\n'
            '                    },\n'
            '                },\n'
            '            ]\n'
            '            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}\n\n'
            '        elif method == "tools/call":\n'
            '            name = params.get("name")\n'
            '            arguments = params.get("arguments", {})\n'
            '            if name == "cognee_recall":\n'
            '                res = engine.recall_memory(arguments.get("query", ""))\n'
            '                return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": res["memory_prompt_block"]}]}}\n'
            '            elif name == "cognee_cognify":\n'
            '                res = engine.cognify_codebase(Path(arguments.get("path", ".")))\n'
            '                return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}}\n\n'
            '        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}\n'
            '    except Exception as e:\n'
            '        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}\n\n'
            'def main():\n'
            '    for line in sys.stdin:\n'
            '        if not line.strip():\n'
            '            continue\n'
            '        resp = handle_request(line)\n'
            '        sys.stdout.write(json.dumps(resp) + "\\n")\n'
            '        sys.stdout.flush()\n\n'
            'if __name__ == "__main__":\n'
            '    main()\n'
        )
        server_file = self.output_dir / "mcp_server.py"
        with open(server_file, "w", encoding="utf-8") as f:
            f.write(server_code)
        server_file.chmod(0o755)
        return server_file

    def export_all_bridges(self) -> Dict[str, str]:
        """Export all plugin configurations and server scripts."""
        claude_mcp = self.generate_claude_code_config()
        openclaw_cfg = self.generate_openclaw_config()
        py_server = self.generate_python_mcp_server()

        return {
            "claude_code_mcp": str(claude_mcp),
            "openclaw_plugin": str(openclaw_cfg),
            "mcp_server_script": str(py_server),
        }
