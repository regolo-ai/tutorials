"""
feedback_controller.py
======================
Nodo FEEDBACK del diagramma TWV — Retry / Reassign.

Il Verifier RACCOMANDA un'azione. Il Controller la CONFERMA o la DEGRADA
in base ai limiti di sicurezza (max_retries, max_reassigns, max_replans).

Logica di escalation:
    RETRY esaurito    -> REASSIGN (o REPLAN se anche reassign esaurito)
    REASSIGN esaurito -> REPLAN
    REPLAN esaurito   -> RETRY forzato finale
"""
from __future__ import annotations
from config import settings
from models import FeedbackAction, SessionState, VerificationReport

class FeedbackController:
    """Decision engine puro (nessuna LLM call) del loop TWV."""

    def decide(self, state: SessionState, report: VerificationReport) -> FeedbackAction:
        if report.status.value == "OK":
            return FeedbackAction.FINISH

        action = report.recommended_action

        if action == FeedbackAction.RETRY:
            if state.retry_count >= settings.max_retries:
                return (FeedbackAction.REASSIGN
                        if state.reassign_count < settings.max_reassigns
                        else FeedbackAction.REPLAN)

        if action == FeedbackAction.REASSIGN:
            if state.reassign_count >= settings.max_reassigns:
                return FeedbackAction.REPLAN

        if action == FeedbackAction.REPLAN:
            if state.replan_count >= settings.max_replans:
                return FeedbackAction.RETRY

        return action
