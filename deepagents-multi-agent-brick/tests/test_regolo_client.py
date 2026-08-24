"""Tests for Regolo API Client & Offline Simulator."""

import pytest
from core.regolo_client import RegoloClient
import config


def test_regolo_client_initialization():
    client = RegoloClient(api_key="test_key", base_url="https://api.regolo.ai/v1")
    assert client.base_url == "https://api.regolo.ai/v1"
    assert client.api_key == "test_key"


def test_regolo_client_chat_completion_simulation():
    client = RegoloClient(api_key="")
    resp = client.chat_completion(
        model=config.REGOLO_MODEL,
        messages=[{"role": "user", "content": "Explain Brick Semantic Routing"}],
        max_tokens=500,
    )
    assert "content" in resp
    assert len(resp["content"]) > 0
    assert resp["prompt_tokens"] > 0
    assert resp["completion_tokens"] > 0
    assert resp["total_tokens"] == resp["prompt_tokens"] + resp["completion_tokens"]
    assert resp["latency_sec"] > 0


def test_regolo_client_evaluate_complexity():
    client = RegoloClient()
    eval_res = client.evaluate_complexity(
        task_description="Synthesize FastMCP server with Pydantic V2 schemas and AST validation",
        role="code_executor",
        tools_requested=["write_mcp_tool", "run_sandbox_tests"],
        current_budget_ratio=0.85,
    )
    assert "complexity_score" in eval_res
    assert 1.0 <= eval_res["complexity_score"] <= 10.0
    assert eval_res["recommended_tier"] in ("FAST", "BALANCED", "REASONING", "DOWNSCALED")
    assert "recommended_model" in eval_res
    assert "routing_reasoning" in eval_res
