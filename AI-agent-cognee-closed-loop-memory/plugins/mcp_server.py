#!/usr/bin/env python3
"""Regolo.ai + Cognee MCP Memory Server for Claude Code & OpenClaw."""
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.cognee_engine import CogneeMemoryEngine

engine = CogneeMemoryEngine()

def handle_request(line: str):
    try:
        req = json.loads(line)
        method = req.get("method")
        params = req.get("params", {})
        req_id = req.get("id")

        if method == "tools/list":
            tools = [
                {
                    "name": "cognee_recall",
                    "description": "Recall ADRs, past CI fixes, and conventions from Cognee memory graph.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
                {
                    "name": "cognee_cognify",
                    "description": "Index directory or codebase into Cognee memory graph.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if name == "cognee_recall":
                res = engine.recall_memory(arguments.get("query", ""))
                return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": res["memory_prompt_block"]}]}}
            elif name == "cognee_cognify":
                res = engine.cognify_codebase(Path(arguments.get("path", ".")))
                return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}

def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        resp = handle_request(line)
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
