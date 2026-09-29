"""
Deterministic Operational Priority Policy for Insurance Intake.
Enforces business rules and life safety triggers through deterministic code.
Crucial invariant: Never relies on probabilistic model inference to determine
whether a message involves life safety, active flooding, or structural hazards.
"""

import re

# Deterministic safety patterns that immediately escalate a ticket to HIGH priority
URGENT_PATTERNS = [
    # Electrical and utility fire hazards
    re.compile(r"\b(electrical panel|power lines?|live wire|gas leak)\b", re.IGNORECASE),
    # Active structural water ingress and flooding
    re.compile(r"\b(burst pipe|active leak|flooding|water rising)\b", re.IGNORECASE),
    # Structural collapse and uninhabitable building damage
    re.compile(r"\b(structural collapse|roof collapse|uninhabitable)\b", re.IGNORECASE),
    # Bodily injury, medical emergency, or fatalities
    re.compile(r"\b(bodily injury|hospital|ambulance|fatal)\b", re.IGNORECASE),
]


def evaluate_agency_priority(text: str) -> str:
    """
    Evaluates operational priority through deterministic business policy.

    Args:
        text: Raw sanitized text of the customer message.

    Returns:
        'high' if any urgent pattern is detected, otherwise 'standard'.
    """
    if not text:
        return "standard"

    for pattern in URGENT_PATTERNS:
        if pattern.search(text):
            return "high"

    return "standard"
