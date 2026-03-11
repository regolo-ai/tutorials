"""Test suite for Qwen 3.5 122b LLMaaS tutorial project."""

from __future__ import annotations

from config import get_settings
from regolo_client import RegoloClient
from use_cases.use_case_1_boilerplate import build_fastapi_prompt
from use_cases.use_case_3_rag import retrieve
from use_cases.use_case_4_structured_output import clean_json_block


def test_prompt_builder_contains_required_endpoints() -> None:
    prompt = build_fastapi_prompt(
        resource_name="Order",
        fields=[{"name": "id", "type": "int"}, {"name": "amount", "type": "float"}],
    )
    assert "GET /list" in prompt
    assert "POST /create" in prompt
    assert "DELETE /order/{id}" in prompt


def test_rag_retrieve_returns_top_k() -> None:
    docs = retrieve("How does pricing work?", top_k=2)
    assert len(docs) == 2
    assert all(isinstance(d, str) and d for d in docs)


def test_clean_json_block() -> None:
    raw = "```json\n{\"title\": \"Backend Engineer\"}\n```"
    assert clean_json_block(raw) == '{"title": "Backend Engineer"}'


def test_live_regolo_chat_completion() -> None:
    settings = get_settings()
    client = RegoloClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        reasoning_effort=settings.reasoning_effort,
    )
    out = client.chat_completion(
        messages=[
            {"role": "system", "content": "You are concise."},
            {"role": "user", "content": "Reply with exactly: Regolo live test ok"},
        ]
    )
    assert isinstance(out, str)
    assert len(out.strip()) > 0
