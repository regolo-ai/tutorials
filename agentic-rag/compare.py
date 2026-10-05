from baseline import run_baseline_rag
from agent import run_agentic_rag
from tui import render_tui_dashboard


def run_comparison(
    question: str, top_k: int = 2, max_rounds: int = 4, api_key: str = ""
) -> dict:
    # comparative empirical execution between baseline and hierarchical agentic rag
    baseline_result = run_baseline_rag(
        question=question, top_k=top_k, api_key=api_key
    )
    agentic_result = run_agentic_rag(
        question=question, max_rounds=max_rounds, api_key=api_key
    )

    tui_display = render_tui_dashboard(
        question=question,
        baseline_data=baseline_result,
        agentic_data=agentic_result,
    )

    return {
        "question": question,
        "baseline": baseline_result,
        "agentic": agentic_result,
        "summary_report": tui_display,
    }
