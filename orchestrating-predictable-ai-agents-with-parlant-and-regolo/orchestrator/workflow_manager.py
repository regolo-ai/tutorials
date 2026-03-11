"""Workflow manager that combines deterministic policy and LLM generation."""

from __future__ import annotations

from agents.parlant_agent import ParlantPolicyAgent
from agents.regolo_agent import RegoloAgent


class WorkflowManager:
    """Orchestrates Parlant-style policy controls with Regolo generation."""

    def __init__(self, policy_agent: ParlantPolicyAgent, regolo_agent: RegoloAgent) -> None:
        self.policy_agent = policy_agent
        self.regolo_agent = regolo_agent

    def run(self, user_input: str) -> str:
        decision = self.policy_agent.decide(user_input)

        system_prompt = (
            "You are a reliable assistant that must follow policy constraints exactly. "
            f"Intent: {decision.intent}. "
            f"Style: {decision.style}. "
            f"Return at most {decision.max_bullets} bullet points when listing items. "
            "If unsure, state assumptions clearly."
        )

        return self.regolo_agent.complete(system_prompt=system_prompt, user_prompt=user_input)
