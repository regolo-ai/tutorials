"""Tests for Budget Controller & Cost Telemetry."""

import pytest
from core.budget_controller import BudgetController


def test_budget_controller_initialization():
    controller = BudgetController(total_budget=25000)
    controller.clear()
    assert controller.total_budget == 25000
    assert controller.get_residual_budget() == 25000
    assert controller.get_budget_ratio() == 1.0


def test_budget_controller_record_step():
    controller = BudgetController(total_budget=10000)
    controller.clear()

    event = controller.record_step(
        subagent_key="planner",
        role_name="Deep Agent Planner",
        model="qwen3.5-122b",
        stage="1_planning",
        prompt_tokens=1000,
        completion_tokens=500,
        latency_sec=1.2,
        routing_tier="REASONING",
    )

    assert event.total_tokens == 1500
    assert event.cost_regolo_usd > 0
    assert event.cost_frontier_usd > event.cost_regolo_usd
    assert controller.get_residual_budget() == 8500
    assert controller.get_budget_ratio() == 0.85

    summary = controller.get_summary()
    assert summary["total_tokens"] == 1500
    assert summary["cost_savings_usd"] > 0
    assert summary["savings_percentage"] > 50.0
    controller.clear()
