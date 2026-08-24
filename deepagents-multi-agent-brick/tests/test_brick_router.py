"""Tests for Brick Semantic Router."""

import pytest
from core.brick_router import BrickRouter, RoutingDecision
from core.regolo_client import RegoloClient
import config


def test_brick_router_initialization():
    router = BrickRouter()
    matrix = router.get_routing_matrix()
    assert len(matrix) >= 6
    roles = [r["subagent_key"] for r in matrix]
    assert "planner" in roles
    assert "researcher" in roles
    assert "code_executor" in roles
    assert "reviewer" in roles


def test_brick_router_standard_routing():
    router = BrickRouter()
    decision = router.route_subagent(
        subagent_key="researcher",
        task_description="Extract parameters from vector store API",
        residual_budget=20000,
        total_budget=25000,
    )
    assert isinstance(decision, RoutingDecision)
    assert decision.subagent_key == "researcher"
    assert decision.selected_model in ("gpt-oss-20b", "GLM-5.2", "qwen3.5-122b")
    assert decision.token_limit > 0
    assert decision.timeout_sec > 0
    assert len(decision.reasoning) > 0


def test_brick_router_force_escalation():
    router = BrickRouter()
    decision = router.route_subagent(
        subagent_key="planner",
        task_description="Complex multi-tiered dependency graph resolution with high failure risk",
        residual_budget=20000,
        total_budget=25000,
        force_escalate=True,
    )
    assert decision.is_escalated is True
    assert decision.selected_model == "qwen3.5-122b"
    assert decision.routing_tier == "ESCALATED"


def test_brick_router_budget_downscaling():
    router = BrickRouter()
    # Residual budget is very low (10% remaining)
    decision = router.route_subagent(
        subagent_key="report_writer",
        task_description="Generate markdown summary documentation",
        residual_budget=2000,
        total_budget=25000,
    )
    assert decision.is_downscaled is True
    assert decision.selected_model == "gpt-oss-20b"
    assert decision.routing_tier == "DOWNSCALED"
