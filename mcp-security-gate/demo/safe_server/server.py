#!/usr/bin/env python3
"""
REGOLO Demo - Safe Vetted MCP Calculator Server
Standard, legitimate arithmetic tool with concise, functional description.
"""

import json
import sys
import time


def handle_initialize(msg_id):
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "safe-calculator-server",
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
                    "name": "calculate",
                    "description": "Perform basic arithmetic calculations (addition, subtraction, multiplication, division).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": ["add", "subtract", "multiply", "divide"],
                                "description": "The arithmetic operation to perform."
                            },
                            "a": {
                                "type": "number",
                                "description": "The first operand."
                            },
                            "b": {
                                "type": "number",
                                "description": "The second operand."
                            }
                        },
                        "required": ["operation", "a", "b"]
                    }
                }
            ]
        }
    }


def handle_tool_call(msg_id, params):
    name = params.get("name")
    args = params.get("arguments", {})
    if name == "calculate":
        op = args.get("operation")
        a = float(args.get("a", 0))
        b = float(args.get("b", 0))
        if op == "add":
            res = a + b
        elif op == "subtract":
            res = a - b
        elif op == "multiply":
            res = a * b
        elif op == "divide":
            res = a / b if b != 0 else "Error: Division by zero"
        else:
            res = "Error: Unknown operation"
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": str(res)}]
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
