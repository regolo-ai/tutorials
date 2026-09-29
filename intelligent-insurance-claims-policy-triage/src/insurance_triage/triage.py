"""
End-to-End Orchestration Pipeline for Insurance Claims & Policy Triage.
Coordinates the three decoupled triage signals:
1. Operational Priority: Evaluated deterministically via policy regex (life safety & asset hazards).
2. Intent Category: Evaluated locally via non-autoregressive SetFit bi-encoder in ~8ms.
3. Processing Complexity: Evaluated via Brick Complexity Pro on Regolo EU gateway.
4. Case Brief Synthesis: Synthesized adaptively using sovereign open-weight models.
Every exception or uncertain threshold fails closed to a human review queue.
"""

import logging
from typing import Any, Dict

from insurance_triage.classifier import classify_intent
from insurance_triage.complexity import grade_complexity
from insurance_triage.models import TriageOutput
from insurance_triage.policy import evaluate_agency_priority
from insurance_triage.synthesizer import draft_case_brief

logger = logging.getLogger(__name__)


def triage_intake_message(raw_text: str) -> TriageOutput:
    """
    Executes the full triage evaluation pipeline for an incoming policyholder communication.

    Args:
        raw_text: Unstructured text of the incoming email or web ticket.

    Returns:
        TriageOutput object containing status, category, complexity, priority, and brief.
    """
    clean_text = raw_text.strip()
    if not clean_text:
        return TriageOutput(
            status="manual_review",
            reason="empty_payload",
            priority="standard",
        )

    # Context window guard for bi-encoders (512 tokens / approx. 2000 characters)
    if len(clean_text) > 2200:
        logger.info("Message exceeds single-pass context budget; trimming for intent classification.")
        eval_text = clean_text[:2200]
    else:
        eval_text = clean_text

    # 1. Deterministic Priority Evaluation (Safety & Emergency Invariant)
    priority = evaluate_agency_priority(eval_text)

    # 2. Local Intent Classification (SetFit Bi-Encoder, 5 to 8 ms)
    cat_result = classify_intent(eval_text)
    if cat_result.get("status") != "confident":
        return TriageOutput(
            status="manual_review",
            category=cat_result.get("category"),
            priority=priority,
            confidence=cat_result.get("confidence"),
            p_abstain=cat_result.get("p_abstain"),
            reason=f"category_{cat_result.get('status')}_{cat_result.get('reason')}",
            metrics=cat_result,
        )

    category = cat_result["category"]

    # 3. Cognitive Complexity Routing via Brick on Regolo
    complexity = grade_complexity(eval_text, category)
    if complexity is None:
        return TriageOutput(
            status="manual_review",
            category=category,
            priority=priority,
            confidence=cat_result.get("confidence"),
            p_abstain=cat_result.get("p_abstain"),
            reason="invalid_complexity_response",
        )

    # 4. Adaptive Case Brief Synthesis via Sovereign EU Model
    try:
        brief = draft_case_brief(clean_text, category, complexity, priority)
        return TriageOutput(
            status="awaiting_operator_review",
            category=category,
            complexity=complexity,
            priority=priority,
            confidence=cat_result.get("confidence"),
            p_abstain=cat_result.get("p_abstain"),
            brief=brief,
        )
    except Exception as e:
        logger.error(f"Error during case brief synthesis: {e}")
        return TriageOutput(
            status="manual_review",
            category=category,
            complexity=complexity,
            priority=priority,
            confidence=cat_result.get("confidence"),
            p_abstain=cat_result.get("p_abstain"),
            reason="synthesis_validation_failure",
        )
