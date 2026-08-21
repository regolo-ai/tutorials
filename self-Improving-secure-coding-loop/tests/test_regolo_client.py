"""Unit tests for Regolo API Client & Telemetry."""

import json
from unittest.mock import MagicMock, patch
import pytest

import config
from core.regolo_client import RegoloClient
from core.brick_governance import get_telemetry_summary, clear_telemetry


def test_regolo_client_initialization():
    client = RegoloClient(base_url="https://api.regolo.ai/v1")
    assert "regolo.ai" in client.base_url
    assert client.model == config.REGOLO_MODEL


def test_regolo_client_missing_key_error():
    client = RegoloClient(api_key="")
    with pytest.raises(RuntimeError) as excinfo:
        client.chat_completion(stage="classify", user_prompt="Test")
    assert "REGOLO_API_KEY is not configured" in str(excinfo.value)


def test_json_parsing_and_markdown_stripping():
    client = RegoloClient()
    # Test with ```json ... ```
    raw_markdown = '```json\n{"intent": "security_fix", "score": 9.5}\n```'
    parsed = client.parse_json_response(raw_markdown)
    assert parsed["intent"] == "security_fix"
    assert parsed["score"] == 9.5

    # Test with plain ``` ... ```
    raw_plain = '```\n{"status": "ok"}\n```'
    parsed2 = client.parse_json_response(raw_plain)
    assert parsed2["status"] == "ok"


def test_evaluate_complexity_heuristic():
    client = RegoloClient()
    score = client._compute_heuristic_complexity(
        task="Remediate SQL injection vulnerability in user search",
        role="Open SWE Planner",
        tools=["cognee_query"],
    )
    assert 1.0 <= score <= 10.0
    tier, model = client._tier_from_score(score, budget_ratio=1.0)
    assert tier in ("FAST", "BALANCED", "REASONING", "DOWNSCALED")
    assert model in ("gpt-oss-20b", "GLM-5.2", "qwen3.5-122b", "Llama-3.3-70B-Instruct")


def test_chat_completion_with_mocked_openai():
    clear_telemetry()
    client = RegoloClient(api_key="regolo_test_key_12345")

    mock_openai = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"intent": "security_vulnerability_remediation", "risk_level": "CRITICAL"}'
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 150
    mock_usage.completion_tokens = 45

    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage = mock_usage
    mock_openai.chat.completions.create.return_value = mock_resp

    client.client = mock_openai
    client.is_live = True

    res = client.chat_completion(
        stage="classify",
        system_prompt="Classify intent",
        user_prompt="SQL Injection in auth service",
        json_mode=True,
    )

    assert res["prompt_tokens"] == 150
    assert res["completion_tokens"] == 45
    assert res["total_tokens"] == 195
    assert "intent" in res["content"]

    # Verify telemetry recorded
    telemetry = get_telemetry_summary()
    assert telemetry["events_count"] >= 1
    assert telemetry["total_tokens"] == 195
    assert telemetry["total_regolo_cost_usd"] > 0
