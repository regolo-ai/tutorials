#!/usr/bin/env python3
"""
Regolo Context Engineering 101 — Unified MCP Server (`regolo_harness_mcp.py`)
Plugs the 4 Context Engineering harness pieces directly into OpenCode, Claude Code, and Codex CLI:
  1. `load_skill_on_demand` / `format_concise_tool` (Part 1: Progressive Disclosure)
  2. `offload_and_delegate` (Part 2: Retrieve, Offload, Delegate via Qwen3-Embedding-8B & brick-v1-beta)
  3. `reversible_compact_history` (Part 3: Reversible Compaction & Cache-Safe Memory)
  4. `init_or_verify_feature_list` (Part 4: Long-Running Initializer / Worker / Evaluator Gate)
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

from piece1_progressive_skills import ProgressiveSkillRegistry, format_tool_response
from piece2_retrieve_offload_delegate import offload_tool_output, delegate_chunk_analyst
from piece3_compaction_and_cache_memory import reversible_compact
from piece4_long_running_harness import initialize_harness

TOOLS = [
    {
        "name": "load_skill_on_demand",
        "description": "Load full instructions for a named skill only when needed (progressive disclosure).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "Exact folder name of the skill to load."},
                "response_format": {"type": "string", "enum": ["concise", "detailed"], "default": "concise"},
            },
            "required": ["skill_name"],
        },
    },
    {
        "name": "offload_and_delegate",
        "description": "Offload a large tool payload to .harness/large_tool_results/ and optionally delegate reading to brick-v1-beta.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "raw_output": {"type": "string"},
                "question": {"type": "string", "description": "Optional question for the brick-v1-beta chunk-analyst subagent."},
            },
            "required": ["tool_name", "raw_output"],
        },
    },
    {
        "name": "reversible_compact_history",
        "description": "Archive full session history to .harness/conversation_history/<session_id>.md and return a compact brick-v1-beta checkpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "messages": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["session_id", "messages"],
        },
    },
    {
        "name": "init_feature_ledger",
        "description": "Initialize .harness/long_running_demo/feature_list.json and progress.txt for multi-session execution.",
        "inputSchema": {
            "type": "object",
            "properties": {"spec": {"type": "string"}},
            "required": ["spec"],
        },
    },
]


def handle_rpc(req: dict) -> dict | None:
    method = req.get("method")
    req_id = req.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "regolo-context-harness", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        api_key = os.environ.get("REGOLO_API_KEY", "")
        if name == "load_skill_on_demand":
            reg = ProgressiveSkillRegistry(Path("~/.claude/skills"))
            text = reg.load_skill(args["skill_name"])
            if args.get("response_format", "concise") == "concise":
                text = "\n".join(text.splitlines()[:40])
            out = text
        elif name == "offload_and_delegate":
            off = offload_tool_output(args["tool_name"], args["raw_output"])
            if args.get("question") and off.get("saved_path") and api_key:
                sub = delegate_chunk_analyst(off["saved_path"], args["question"], api_key)
                out = json.dumps({"offload": off, "subagent": sub}, indent=2)
            else:
                out = json.dumps(off, indent=2)
        elif name == "reversible_compact_history":
            res = reversible_compact(args["messages"], args["session_id"], api_key)
            out = json.dumps(res, indent=2)
        elif name == "init_feature_ledger":
            p = initialize_harness(args["spec"])
            out = f"Initialized {p}"
        else:
            out = f"Unknown tool: {name}"
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": out}]}}
    return None


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        r1 = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        r2 = handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert r1 and r2 and len(r2["result"]["tools"]) == 4
        print("MCP JSON-RPC stdio self-test PASSED: 4 tools registered:", [t["name"] for t in r2["result"]["tools"]])
        sys.exit(0)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        resp = handle_rpc(json.loads(line))
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
