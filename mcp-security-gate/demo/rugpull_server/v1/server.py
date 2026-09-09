#!/usr/bin/env python3
"""
REGOLO Demo - Rug-Pull Target Server v1.0.0 (Clean Baseline)
Legitimate string formatting tool initially audited and approved by the developer.
"""

import json
import sys
import time

CLEAN_DESCRIPTION = "Transform and format text strings into title case, upper case, or lower case."


def handle_initialize(msg_id):
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "text-formatter-server",
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
                    "name": "format_text",
                    "description": CLEAN_DESCRIPTION,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The input text to format."
                            },
                            "style": {
                                "type": "string",
                                "enum": ["upper", "lower", "title"],
                                "description": "Target capitalization style."
                            }
                        },
                        "required": ["text", "style"]
                    }
                }
            ]
        }
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
