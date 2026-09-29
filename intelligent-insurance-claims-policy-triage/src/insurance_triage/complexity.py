"""
Semantic Complexity Routing Module using Brick Complexity Pro.
Grades incoming customer requests into 'easy', 'medium', or 'hard' based on
cognitive and structural synthesis demand, rather than character length.
Enables adaptive model tier routing to minimize token costs on routine tasks.
"""

import logging
import os
import re
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

_openai_client = None


def get_openai_client() -> OpenAI:
    """Initializes and returns a singleton OpenAI-compatible client for Regolo.ai."""
    global _openai_client
    if _openai_client is None:
        base_url = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
        api_key = os.environ.get("REGOLO_API_KEY", "")
        _openai_client = OpenAI(base_url=base_url, api_key=api_key or "mock-key")
    return _openai_client


def parse_complexity_grade(raw_content: str) -> Optional[str]:
    """
    Extracts 'easy', 'medium', or 'hard' from model completion,
    handling markdown bolding or surrounding explanation tokens.
    """
    cleaned = raw_content.lower()
    match = re.search(r"\b(easy|medium|hard)\b", cleaned)
    if match:
        return match.group(1)
    return None


def evaluate_mock_complexity(text: str, category: str) -> str:
    """
    Deterministic semantic complexity heuristic mimicking brick-complexity-pro
    for offline benchmark execution when no external API key is provided.
    Evaluates clause density, legal entanglement, and structural ambiguity.
    """
    lower = text.lower()

    # Highly complex legal, corporate, or multi-party entanglement
    hard_signals = [
        "probate", "estate", "llc", "lawsuit", "attorney", "subrogation",
        "liability dispute", "disputed", "fraud", "commercial umbrella",
        "insolvency", "court", "deceased", "multiple parties", "litigation"
    ]
    if any(sig in lower for sig in hard_signals):
        return "hard"

    # Moderate complexity: estimates, deductibles, multiple items
    words = text.split()
    medium_signals = [
        "estimate", "invoice", "deductible", "contractor", "depreciation",
        "itemized", "appraisal", "disagreement"
    ]
    if any(sig in lower for sig in medium_signals) or len(words) > 80:
        return "medium"

    # Concise, straightforward single-intent notifications
    return "easy"


def grade_complexity(text: str, category: str) -> Optional[str]:
    """
    Calls brick-complexity-pro on the Regolo European inference gateway.
    Returns: 'easy', 'medium', 'hard', or None if the response fails validation.
    """
    api_key = os.environ.get("REGOLO_API_KEY")
    if not api_key:
        return evaluate_mock_complexity(text, category)

    client = get_openai_client()
    model_name = os.environ.get("REGOLO_COMPLEXITY_MODEL", "brick-complexity-pro")
    prompt = (
        "Assess the cognitive and structural complexity of preparing an internal "
        "intake case brief for this insurance request. "
        "Return only one word: easy, medium, or hard.\n\n"
        f"Declared Category: {category}\n"
        f"Customer Message:\n{text}"
    )

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=64,
        )
        raw_text = completion.choices[0].message.content or ""
        grade = parse_complexity_grade(raw_text)
        if grade:
            return grade
        logger.warning(f"Unexpected complexity grade returned from API: {raw_text}")
        return None
    except Exception as e:
        logger.error(f"Error calling {model_name}: {e}")
        return None
