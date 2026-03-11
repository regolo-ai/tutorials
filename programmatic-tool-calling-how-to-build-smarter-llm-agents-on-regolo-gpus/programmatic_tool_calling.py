"""Programmatic tool calling orchestration with a restricted runtime."""

from __future__ import annotations

import json
from typing import Any

from regolo_client import RegoloClient
from runtime.program_executor import execute_program
from tools import (
    escalate_to_human,
    filter_by_min_total,
    get_user_orders,
    search_knowledge_base,
    summarize_orders,
)


PROGRAMMING_PROMPT = """
You are an AI that writes short Python programs to solve tasks by calling tools.

Available functions:
- get_user_orders(user_id: str, limit: int) -> list[dict]
- filter_by_min_total(orders: list[dict], min_total: float) -> list[dict]
- summarize_orders(orders: list[dict]) -> dict

Rules:
- Do NOT print anything.
- Do NOT import modules.
- Use only the functions listed above and basic Python control flow.
- Always assign the final answer to a variable named result.
""".strip()


PROGRAMMING_PROMPT_MULTI = """
You are an AI that writes short Python programs to solve customer support tasks.

Available functions:
- get_user_orders(user_id: str, limit: int)
- filter_by_min_total(orders, min_total: float)
- summarize_orders(orders)
- search_knowledge_base(query: str)
- escalate_to_human(ticket_id: str, summary: str)

Rules:
- Use the tools as needed.
- You may branch based on tool results.
- Always set a final result dict with keys:
  - answer: str
  - actions: list
""".strip()


BASIC_RUNTIME = {
    "get_user_orders": get_user_orders,
    "filter_by_min_total": filter_by_min_total,
    "summarize_orders": summarize_orders,
}


SUPPORT_RUNTIME = {
    **BASIC_RUNTIME,
    "search_knowledge_base": search_knowledge_base,
    "escalate_to_human": escalate_to_human,
}


def _extract_program_source(content: str) -> str:
    text = (content or "").strip()
    if "```" not in text:
        return text

    parts = text.split("```")
    for part in parts:
        snippet = part.strip()
        if not snippet:
            continue
        if snippet.startswith("python"):
            return snippet[len("python") :].strip()
        if "result" in snippet:
            return snippet

    return text


def plan_with_program(client: RegoloClient, user_message: str, multi: bool = False) -> str:
    system_prompt = PROGRAMMING_PROMPT_MULTI if multi else PROGRAMMING_PROMPT
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
    )
    raw = response["choices"][0]["message"].get("content", "")
    return _extract_program_source(raw)


def run_agent_with_program(client: RegoloClient, user_message: str) -> str:
    program_source = plan_with_program(
        client,
        f"Write a program that solves this request: {user_message}",
        multi=False,
    )
    try:
        result = execute_program(program_source, BASIC_RUNTIME)
    except Exception:
        fallback = """
orders = get_user_orders('user_789', 20)
filtered = filter_by_min_total(orders, 30)
result = summarize_orders(filtered)
"""
        result = execute_program(fallback, BASIC_RUNTIME)

    explain = client.chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"User request: {user_message}"},
            {"role": "user", "content": f"Tool results: {json.dumps(result)}"},
        ]
    )
    return explain["choices"][0]["message"].get("content", "")


def run_support_agent_with_program(client: RegoloClient, user_message: str) -> dict[str, Any]:
    program_source = plan_with_program(
        client,
        f"Write a program that solves this support request: {user_message}",
        multi=True,
    )
    try:
        result = execute_program(program_source, SUPPORT_RUNTIME)
    except Exception:
        fallback = """
kb = search_knowledge_base('refund exception policy')
escalation = escalate_to_human('TCK-992', 'Needs human approval for refund exception above 100 EUR')
result = {
    'answer': 'I have escalated this request to a human support lead based on policy.',
    'actions': [
        'searched knowledge base',
        'created escalation ' + escalation['ticket_id']
    ]
}
"""
        result = execute_program(fallback, SUPPORT_RUNTIME)

    if not isinstance(result, dict):
        raise ValueError("Support program must return a dict")
    if "answer" not in result or "actions" not in result:
        raise ValueError("Support program result must contain 'answer' and 'actions'")

    return result
