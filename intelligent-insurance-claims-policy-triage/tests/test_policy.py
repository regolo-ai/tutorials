import pytest

from insurance_triage.policy import evaluate_agency_priority


def test_priority_detects_electrical_hazard():
    text = "Water is coming through the ceiling and reaching the electrical panel."
    assert evaluate_agency_priority(text) == "high"


def test_priority_detects_active_flooding():
    text = "We have a burst pipe in the basement and water rising quickly."
    assert evaluate_agency_priority(text) == "high"


def test_priority_detects_structural_damage():
    text = "Part of the roof collapsed after the storm, house is uninhabitable."
    assert evaluate_agency_priority(text) == "high"


def test_priority_detects_bodily_injury():
    text = "A customer slipped in the lobby, ambulance was called to hospital."
    assert evaluate_agency_priority(text) == "high"


def test_priority_returns_standard_for_routine_endorsement():
    text = "I would like to change my mailing address for policy number 88392."
    assert evaluate_agency_priority(text) == "standard"


def test_priority_returns_standard_for_empty_text():
    assert evaluate_agency_priority("") == "standard"
