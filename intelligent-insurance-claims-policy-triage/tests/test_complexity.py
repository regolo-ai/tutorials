import pytest
from unittest.mock import MagicMock, patch

from insurance_triage.complexity import grade_complexity, evaluate_mock_complexity


def test_mock_complexity_easy_query():
    text = "A pipe burst this morning. Policy 12345."
    tier = evaluate_mock_complexity(text, "claims_intake")
    assert tier == "easy"


def test_mock_complexity_hard_query():
    text = (
        "My husband passed away last month, the commercial estate is in probate court, "
        "and I need to know if our commercial umbrella covers the farm tractor leased under his LLC."
    )
    tier = evaluate_mock_complexity(text, "customer_query")
    assert tier == "hard"


def test_mock_complexity_medium_query():
    text = (
        "We had minor roof hail damage last week. The roofer estimated 4000 euros. "
        "I have invoices attached and need to know the deductible."
    )
    tier = evaluate_mock_complexity(text, "claims_intake")
    assert tier in {"easy", "medium"}


def test_grade_complexity_with_live_mock():
    # When no API key is present, fallback to local evaluator
    with patch.dict("os.environ", {}, clear=True):
        res = grade_complexity("A pipe burst this morning.", "claims_intake")
        assert res in {"easy", "medium", "hard"}


def test_grade_complexity_rejects_invalid_api_response():
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "extremely_difficult"  # Invalid! Not easy/medium/hard
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with patch("insurance_triage.complexity.get_openai_client", return_value=mock_client), \
         patch.dict("os.environ", {"REGOLO_API_KEY": "test-key"}):
        res = grade_complexity("Some claim", "claims_intake")
        assert res is None
