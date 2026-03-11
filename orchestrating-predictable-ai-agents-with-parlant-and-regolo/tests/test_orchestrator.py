"""Tests for predictable orchestration flow."""

from __future__ import annotations

from agents.parlant_agent import ParlantPolicyAgent
from agents.regolo_agent import RegoloAgent
from config import get_settings
from orchestrator.workflow_manager import WorkflowManager


def test_parlant_policy_routing() -> None:
    agent = ParlantPolicyAgent()

    decision = agent.decide("Write a GDPR compliance policy for customer data")

    assert decision.intent == "compliance"
    assert decision.style == "strict_and_cited"
    assert decision.max_bullets == 4


def test_live_regolo_orchestration() -> None:
    settings = get_settings()
    workflow = WorkflowManager(
        policy_agent=ParlantPolicyAgent(),
        regolo_agent=RegoloAgent(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            model=settings.regolo_model,
            temperature=settings.temperature,
        ),
    )

    response = workflow.run("Give me 3 actions to improve incident response runbooks.")

    assert isinstance(response, str)
    assert len(response.strip()) > 0
    assert "incident" in response.lower() or "runbook" in response.lower() or "response" in response.lower()
