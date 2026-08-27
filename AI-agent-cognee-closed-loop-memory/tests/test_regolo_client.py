"""Unit tests for Regolo.ai client and Brick router."""

import pytest
import config
from core.regolo_client import BrickRouter, RegoloClient


def test_brick_router_complexity_evaluation():
    """Verify Brick router selects models appropriately based on task complexity."""
    # High complexity / ADR / causality -> qwen3.5-122b
    model, score, rationale = BrickRouter.evaluate_task("Architectural decision causality conflict in tenant isolation ADR-001")
    assert model == config.MODEL_AGENT_REASONING
    assert score >= 7.0

    # Code implementation -> qwen3-coder-next
    model, score, rationale = BrickRouter.evaluate_task("def search_users(db, query): return patch", context_type="coder")
    assert model == config.MODEL_AGENT_CODER

    # Fast extraction -> gpt-oss-20b
    model, score, rationale = BrickRouter.evaluate_task("extract entities and list relations from text", context_type="extract")
    assert model == config.MODEL_COGNEE_EXTRACT


def test_regolo_client_live_generation():
    """Verify live generation works on Regolo.ai."""
    client = RegoloClient()
    res = client.generate(
        prompt="Respond with OK if connected.",
        stage="chat",
        max_tokens=20,
    )

    assert "content" in res
    assert res["zero_data_retention"] is True
    assert res["total_tokens"] > 0
    assert res["cost_eur"] >= 0.0
    assert res["simulated"] is False


def test_regolo_client_fallback_on_error():
    """Verify client falls back to REGOLO_DEFAULT_MODEL (GLM-5.2) if routed model fails."""
    from unittest.mock import MagicMock, patch

    client = RegoloClient()
    
    # Mock completions.create to fail on initial model, then succeed on GLM-5.2
    mock_success_response = MagicMock()
    mock_success_response.choices = [MagicMock(message=MagicMock(content="Fallback response"))]
    mock_success_response.usage = MagicMock(prompt_tokens=10, completion_tokens=10)

    def side_effect(*args, **kwargs):
        if kwargs.get("model") == "qwen3-coder-next":
            raise RuntimeError("Temporary model outage")
        return mock_success_response

    with patch.object(client.client.chat.completions, "create", side_effect=side_effect):
        res = client.generate(
            prompt="def fix(): pass",
            stage="coder",
            override_model="qwen3-coder-next",
            max_tokens=50,
        )

    assert res["model"] == config.REGOLO_DEFAULT_MODEL
    assert res["content"] == "Fallback response"
    assert config.REGOLO_DEFAULT_MODEL == "GLM-5.2"
