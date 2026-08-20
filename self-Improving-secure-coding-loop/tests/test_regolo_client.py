"""Unit tests for Regolo API Client & Telemetry."""

import pytest
from core.regolo_client import RegoloClient
from core.brick_governance import get_telemetry_summary, clear_telemetry


def test_regolo_client_initialization():
    client = RegoloClient()
    assert client.model == "GLM-5.2"
    assert "regolo.ai" in client.base_url


def test_chat_completion_stages():
    clear_telemetry()
    client = RegoloClient()

    # Test classify stage
    res = client.chat_completion(
        stage="classify",
        system_prompt="Classify intent",
        user_prompt="SQL Injection in auth service",
        json_mode=True,
    )
    assert res["prompt_tokens"] > 0
    assert res["completion_tokens"] > 0
    parsed = client.parse_json_response(res["content"])
    assert "intent" in parsed or "policy_decision" in parsed

    # Check telemetry
    telemetry = get_telemetry_summary()
    assert telemetry["events_count"] >= 1
    assert telemetry["total_tokens"] > 0
    assert telemetry["savings_percentage"] > 0
