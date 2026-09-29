import pytest
from pathlib import Path

from insurance_triage.classifier import SetFitDecisionEngine, INSURANCE_CATEGORIES


def test_setfit_engine_loads_model():
    model_dir = Path("models/setfit-insurance-triage")
    if not model_dir.exists():
        pytest.skip("SetFit model not trained yet; run train.py first")

    engine = SetFitDecisionEngine()
    assert len(engine.categories) == 5
    assert "claims_intake" in engine.categories


def test_setfit_engine_classifies_routine_address_change():
    model_dir = Path("models/setfit-insurance-triage")
    if not model_dir.exists():
        pytest.skip("SetFit model not trained yet; run train.py first")

    engine = SetFitDecisionEngine()
    text = "Please change the primary garaging address on our commercial fleet policy FL-90210 to 458 Industrial Parkway, Suite B."
    result = engine.evaluate(text, INSURANCE_CATEGORIES)

    assert result["selected_option_id"] == "policy_change"
    assert result["confidence"] > 0.50
    assert result["is_abstention"] is False


def test_setfit_engine_handles_empty_input():
    model_dir = Path("models/setfit-insurance-triage")
    if not model_dir.exists():
        pytest.skip("SetFit model not trained yet; run train.py first")

    engine = SetFitDecisionEngine()
    result = engine.evaluate("", INSURANCE_CATEGORIES)
    assert result["is_abstention"] is True
    assert result["selected_option_id"] is None
