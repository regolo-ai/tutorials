"""Run all article use cases in sequence with live Regolo API calls."""

from __future__ import annotations

from config import get_settings
from regolo_client import RegoloClient
from use_cases.use_case_1_boilerplate import generate_fastapi_endpoint
from use_cases.use_case_2_streaming import run_single_stream
from use_cases.use_case_3_rag import answer_with_rag
from use_cases.use_case_4_structured_output import extract_job_posting


def main() -> None:
    settings = get_settings()
    client = RegoloClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        reasoning_effort=settings.reasoning_effort,
    )

    print("\n=== Use Case 1: Boilerplate Generator ===")
    code = generate_fastapi_endpoint(
        client=client,
        resource_name="Product",
        fields=[
            {"name": "id", "type": "int"},
            {"name": "name", "type": "str"},
            {"name": "price", "type": "float"},
            {"name": "in_stock", "type": "bool"},
        ],
    )
    print(code[:900])

    print("\n=== Use Case 2: Streaming Chat ===")
    stream_reply = run_single_stream(
        client=client,
        system_prompt="You are a concise Python code review assistant.",
        user_prompt="Review this function briefly: def add(a,b): return a+b",
    )
    print(stream_reply)

    print("\n=== Use Case 3: RAG ===")
    rag_answer = answer_with_rag(client=client, query="How does Regolo handle data residency?")
    print(rag_answer)

    print("\n=== Use Case 4: Structured Output ===")
    sample_post = (
        "We're hiring a Senior Backend Engineer at TechCorp (Rome, Italy - hybrid). "
        "Need 5+ years with Python, FastAPI, PostgreSQL and Docker. "
        "Salary: EUR 60k-80k/year."
    )
    extracted = extract_job_posting(client=client, raw_text=sample_post)
    print(extracted)


if __name__ == "__main__":
    main()
