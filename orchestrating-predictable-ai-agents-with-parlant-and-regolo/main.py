"""CLI demo for predictable orchestration with Parlant and Regolo."""

from __future__ import annotations

from agents.parlant_agent import ParlantPolicyAgent
from agents.regolo_agent import RegoloAgent
from config import get_settings
from orchestrator.workflow_manager import WorkflowManager


def main() -> None:
    settings = get_settings()
    orchestrator = WorkflowManager(
        policy_agent=ParlantPolicyAgent(),
        regolo_agent=RegoloAgent(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            model=settings.regolo_model,
            temperature=settings.temperature,
        ),
    )

    prompt = "Create a short compliance checklist for handling customer support tickets with PII."
    result = orchestrator.run(prompt)

    print("\n=== User Prompt ===")
    print(prompt)
    print("\n=== Orchestrated Response ===")
    print(result)


if __name__ == "__main__":
    main()
