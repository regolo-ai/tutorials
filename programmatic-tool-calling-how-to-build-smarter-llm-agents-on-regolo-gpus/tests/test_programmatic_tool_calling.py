"""Tests for classic and programmatic tool calling tutorial."""

from __future__ import annotations

from config import get_settings
from regolo_client import RegoloClient
from runtime.program_executor import execute_program
from tools import filter_by_min_total, get_user_orders, summarize_orders


RUNTIME = {
    "get_user_orders": get_user_orders,
    "filter_by_min_total": filter_by_min_total,
    "summarize_orders": summarize_orders,
}


def test_execute_program_happy_path() -> None:
    src = """
orders = get_user_orders('user_789', 3)
filtered = filter_by_min_total(orders, 30)
result = summarize_orders(filtered)
"""
    result = execute_program(src, RUNTIME)
    assert isinstance(result, dict)
    assert result["count"] >= 1


def test_execute_program_blocks_imports() -> None:
    bad = """
import os
result = {'ok': True}
"""
    try:
        execute_program(bad, RUNTIME)
        assert False, "Import should be blocked"
    except ValueError:
        assert True


def test_live_regolo_completion() -> None:
    settings = get_settings()
    client = RegoloClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        reasoning_effort=settings.reasoning_effort,
    )
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": "You are concise."},
            {"role": "user", "content": "Reply with: PTC live test ok"},
        ]
    )
    text = response["choices"][0]["message"].get("content", "")
    assert isinstance(text, str)
    assert len(text.strip()) > 0
