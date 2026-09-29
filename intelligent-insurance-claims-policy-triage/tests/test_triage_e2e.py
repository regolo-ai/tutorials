import pytest

from insurance_triage.triage import triage_intake_message


def test_triage_e2e_urgent_burst_pipe():
    text = (
        "A pipe burst this morning and water is reaching the electrical panel. "
        "My policy number is 12345. I have photos, but I cannot find the claim form."
    )
    result = triage_intake_message(text)

    assert result.status == "awaiting_operator_review"
    assert result.category == "claims_intake"
    assert result.priority == "high"
    assert result.complexity in {"easy", "medium"}
    assert result.brief is not None
    assert "water" in result.brief.summary.lower() or "pipe" in result.brief.summary.lower()
    assert len(result.brief.information_to_check) > 0
    assert len(result.brief.review_flags) > 0


def test_triage_e2e_policy_address_change():
    text = "Please change the primary garaging address on my auto policy to 45 Elm St."
    result = triage_intake_message(text)

    assert result.status == "awaiting_operator_review"
    assert result.category == "policy_change"
    assert result.priority == "standard"
    assert result.complexity in {"easy", "medium"}
    assert result.brief is not None


def test_triage_e2e_abstain_on_irrelevant_query():
    text = "Can you help me solve this quadratic equation: x^2 + 5x + 6 = 0?"
    result = triage_intake_message(text)

    # Must fail to human manual review!
    assert result.status == "manual_review"
    assert "abstain" in result.reason or "uncertain" in result.reason
    assert result.brief is None


def test_triage_e2e_empty_input():
    result = triage_intake_message("")
    assert result.status == "manual_review"
    assert result.reason == "empty_payload"


def test_triage_e2e_oversized_payload_handling():
    # Long text with repeated content
    text = "A pipe burst in the cellar. " * 300
    result = triage_intake_message(text)
    assert result.category == "claims_intake"
