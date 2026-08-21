"""Tests for Brick Semantic Router."""

from unittest.mock import MagicMock
import pytest
import config
from core.brick_router import BrickRouter, RoutingDecision


def test_brick_router_initialization():
    router = BrickRouter()
    matrix = router.get_routing_matrix()
    assert len(matrix) >= 6
    stages = [r["stage_key"] for r in matrix]
    assert "classify" in stages
    assert "plan" in stages
    assert "implement" in stages
    assert "deepsec_scan" in stages
    assert "deepsec_revalidate" in stages
    assert "cognee_extract" in stages


def test_brick_router_standard_routing():
    mock_client = MagicMock()
    mock_client.evaluate_complexity.return_value = {
        "complexity_score": 4.5,
        "recommended_tier": "FAST",
        "recommended_model": "gpt-oss-20b",
        "routing_reasoning": "Standard triage task with low complexity",
        "latency_sec": 0.1,
    }
    router = BrickRouter(client=mock_client)
    decision = router.route_stage(
        stage="classify",
        task_description="Triage incoming issue description for SQL injection",
        residual_budget=20000,
        total_budget=25000,
    )
    assert isinstance(decision, RoutingDecision)
    assert decision.stage_key == "classify"
    assert decision.selected_model == "gpt-oss-20b"
    assert decision.token_limit > 0
    assert decision.timeout_sec > 0
    assert len(decision.reasoning) > 0
    assert decision.is_escalated is False
    assert decision.is_downscaled is False


def test_brick_router_force_escalation():
    mock_client = MagicMock()
    mock_client.evaluate_complexity.return_value = {
        "complexity_score": 8.5,
        "recommended_tier": "REASONING",
        "recommended_model": "qwen3.5-122b",
        "routing_reasoning": "High complexity architecture planning",
        "latency_sec": 0.2,
    }
    router = BrickRouter(client=mock_client)
    decision = router.route_stage(
        stage="plan",
        task_description="Deep architectural refactoring for high-risk vulnerability",
        residual_budget=20000,
        total_budget=25000,
        force_escalate=True,
    )
    assert decision.is_escalated is True
    assert decision.selected_model == "qwen3.5-122b"
    assert decision.routing_tier == "ESCALATED"


def test_brick_router_complexity_threshold_escalation():
    mock_client = MagicMock()
    # High complexity score >= 7.0 triggers dynamic escalation
    mock_client.evaluate_complexity.return_value = {
        "complexity_score": 8.2,
        "recommended_tier": "REASONING",
        "recommended_model": "qwen3.5-122b",
        "routing_reasoning": "Complexity exceeds threshold 7.0",
        "latency_sec": 0.2,
    }
    router = BrickRouter(client=mock_client)
    decision = router.route_stage(
        stage="deepsec_scan",
        task_description="Complex vulnerability scan across multiple interconnected files",
        residual_budget=20000,
        total_budget=25000,
    )
    assert decision.is_escalated is True
    assert decision.selected_model == "qwen3.5-122b"
    assert decision.routing_tier == "ESCALATED"


def test_brick_router_budget_downscaling():
    mock_client = MagicMock()
    mock_client.evaluate_complexity.return_value = {
        "complexity_score": 3.0,
        "recommended_tier": "FAST",
        "recommended_model": "gpt-oss-20b",
        "routing_reasoning": "Routine memory extraction",
        "latency_sec": 0.1,
    }
    router = BrickRouter(client=mock_client)
    # Residual budget is very low (< 25% remaining) on LOW criticality stage
    decision = router.route_stage(
        stage="cognee_extract",
        task_description="Extract knowledge graph nodes",
        residual_budget=2000,
        total_budget=25000,
    )
    assert decision.is_downscaled is True
    assert decision.selected_model == "gpt-oss-20b"
    assert decision.routing_tier == "DOWNSCALED"
