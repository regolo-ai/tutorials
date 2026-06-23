"""models.py — Contratti di dominio per il sistema TWV."""
from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class VerificationStatus(str, Enum):
    OK = "OK"
    FAIL = "FAIL"

class FeedbackAction(str, Enum):
    FINISH   = "FINISH"
    RETRY    = "RETRY"
    REASSIGN = "REASSIGN"
    REPLAN   = "REPLAN"

class PlanPacket(BaseModel):
    """Output strutturato del Thinker."""
    summary: str
    decomposition: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    selected_worker: str
    alternative_workers: List[str] = Field(default_factory=list)
    requires_self_call: bool = False
    thinker_notes: str = ""

class WorkerResult(BaseModel):
    """Output di un tentativo del Worker."""
    worker_id: str
    attempt: int = Field(ge=1)
    content: str

class VerificationReport(BaseModel):
    """Valutazione strutturata del Verifier."""
    status: VerificationStatus
    score: int = Field(ge=1, le=10)
    feedback: str
    evidence: List[str] = Field(default_factory=list)
    failure_type: str = ""
    recommended_action: FeedbackAction = FeedbackAction.RETRY
    recommended_worker: Optional[str] = None

class SessionState(BaseModel):
    """Stato globale della sessione di orchestrazione."""
    user_input: str
    plan: Optional[PlanPacket] = None
    selected_worker: Optional[str] = None
    worker_outputs: List[WorkerResult] = Field(default_factory=list)
    verification_reports: List[VerificationReport] = Field(default_factory=list)
    final_output: Optional[str] = None
    retry_count: int = 0
    reassign_count: int = 0
    replan_count: int = 0

    @property
    def latest_output(self) -> Optional[str]:
        return self.worker_outputs[-1].content if self.worker_outputs else None

    @property
    def latest_report(self) -> Optional[VerificationReport]:
        return self.verification_reports[-1] if self.verification_reports else None
