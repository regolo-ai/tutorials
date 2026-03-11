"""Classic two-step JSON tool calling flow."""

from __future__ import annotations

import json
from typing import Any

from regolo_client import RegoloClient
from tools import get_user_orders


TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_user_orders",
            "description": "Fetch last N orders for a given user id",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["user_id"],
            },
        },
    }
]


def chat_with_tools(client: RegoloClient, user_message: str) -> str:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You are a helpful support assistant."},
        {"role": "user", "content": user_message},
    ]

    first = client.chat_completion(messages=messages, tools=TOOLS_SCHEMA, tool_choice="auto")
    assistant_message = first["choices"][0]["message"]

    tool_calls = assistant_message.get("tool_calls", [])
    if not tool_calls:
        return assistant_message.get("content", "")

    tool_messages: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        name = tool_call["function"]["name"]
        raw_args = tool_call["function"].get("arguments", "{}")

        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}

        if name == "get_user_orders":
            result = get_user_orders(**args)
        else:
            result = {"error": f"unknown tool: {name}"}

        tool_messages.append(
            {
                "tool_call_id": tool_call["id"],
                "role": "tool",
                "name": name,
                "content": json.dumps(result),
            }
        )

    messages.append(assistant_message)
    messages.extend(tool_messages)
    second = client.chat_completion(messages=messages)
    return second["choices"][0]["message"].get("content", "")
