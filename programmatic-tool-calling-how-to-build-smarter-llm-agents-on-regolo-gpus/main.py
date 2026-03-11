"""Run classic and programmatic tool calling demos."""

from __future__ import annotations

from classic_tool_calling import chat_with_tools
from config import get_settings
from programmatic_tool_calling import run_agent_with_program, run_support_agent_with_program
from regolo_client import RegoloClient


def main() -> None:
    settings = get_settings()
    client = RegoloClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        reasoning_effort=settings.reasoning_effort,
    )

    print("\n=== Classic JSON Tool Calling ===")
    classic_reply = chat_with_tools(
        client,
        "Show me my last 2 orders. My id is user_789.",
    )
    print(classic_reply)

    print("\n=== Programmatic Tool Calling ===")
    try:
        programmatic_reply = run_agent_with_program(
            client,
            "Summarize orders above 30 EUR for user_789 and provide totals.",
        )
        print(programmatic_reply)
    except Exception as exc:
        print(f"Programmatic run failed: {exc}")

    print("\n=== Multi-step Support Agent ===")
    try:
        support_result = run_support_agent_with_program(
            client,
            "Customer asks refund exception above 100 EUR for ticket TCK-992.",
        )
        print(support_result)
    except Exception as exc:
        print(f"Support program run failed: {exc}")


if __name__ == "__main__":
    main()
