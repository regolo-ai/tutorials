import pytest

from insurance_triage.classifier import (
    INSURANCE_CATEGORIES,
    classify_intent,
    MockDecisionEngine,
)


def test_taxonomy_has_valid_options():
    assert len(INSURANCE_CATEGORIES) == 5
    ids = {opt.id for opt in INSURANCE_CATEGORIES}
    assert "claims_intake" in ids
    assert "policy_change" in ids
    assert "underwriting_support" in ids
    assert "document_missing" in ids
    assert "customer_query" in ids


def test_classify_claims_intake_high_confidence():
    text = "A pipe burst this morning and water is reaching the electrical panel. Policy 12345."
    res = classify_intent(text)
    assert res["status"] == "confident"
    assert res["category"] == "claims_intake"
    assert res["confidence"] >= 0.85
    assert res["is_abstention"] is False


def test_classify_policy_change():
    text = "Please change the primary garaging address on my auto policy to 45 Elm St."
    res = classify_intent(text)
    assert res["status"] == "confident"
    assert res["category"] == "policy_change"
    assert res["confidence"] >= 0.85


def test_classify_abstains_on_unrelated_text():
    text = "Can you give me the best recipe for chocolate chip cookies?"
    res = classify_intent(text)
    assert res["status"] in {"abstain", "uncertain"}
    if res["status"] == "abstain":
        assert res["is_abstention"] is True


def test_classify_rejects_empty_string():
    res = classify_intent("")
    assert res["status"] in {"abstain", "uncertain"}
