"""Contract test against the real Regolo API. Run with: uv run pytest -m live"""

import os

import pytest
from dotenv import load_dotenv

from conftest import run
from fraudclef.backends import regolo_backend
from fraudclef.policy import load_policy

load_dotenv(".env")


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("REGOLO_API_KEY"), reason="REGOLO_API_KEY not set")
def test_systemone_contract():
    policy = load_policy("policies/retail-eu-explainable.yaml")  # covers noul, choice and score
    questions = {k: q.to_systemone() for k, q in policy.questions.items()}
    state = {"candidate": {"amount": 38.9, "channel": "card_present", "country": "IT"},
             "history_summary": {"median_amount": 48.2, "countries": ["IT"]}}

    async def go():
        backend = regolo_backend()
        try:
            return await backend.decide(state, questions, timeout_s=10)
        finally:
            await backend.aclose()

    result = run(go())
    assert set(result.answers) == set(questions)
    assert result.input_tokens and result.input_tokens > 0
    for qid, q in policy.questions.items():
        a = result.answers[qid]
        assert a["type"] == q.type
        if q.type == "noul":
            assert 0 <= a["noul"] <= 1
        elif q.type == "choice":
            assert a["choice"] in q.criteria and set(a["probabilities"]) == set(q.criteria)
        else:
            assert 0 <= a["score"] <= len(q.criteria) - 1
