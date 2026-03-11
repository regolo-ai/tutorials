"""A tiny deterministic policy agent inspired by Parlant-style orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    """Policy output used to constrain the LLM answer."""

    intent: str
    style: str
    max_bullets: int


class ParlantPolicyAgent:
    """Extract intent and output constraints from the incoming user request."""

    def decide(self, user_input: str) -> PolicyDecision:
        text = user_input.lower()

        if any(k in text for k in ("runbook", "incident", "postmortem")):
            return PolicyDecision(intent="ops_support", style="concise_and_actionable", max_bullets=5)

        if any(k in text for k in ("policy", "gdpr", "compliance", "security")):
            return PolicyDecision(intent="compliance", style="strict_and_cited", max_bullets=4)

        return PolicyDecision(intent="general_assistant", style="clear_and_short", max_bullets=3)
