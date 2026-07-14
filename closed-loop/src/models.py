"""
src/models.py
-------------
Dataclasses for audit trail, usage tracking, and iteration records.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class UsageRecord:
    """Per-call LLM token usage and cost tracking."""
    model: str
    stage: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float
    call_num: int = 1


@dataclass
class IterationRecord:
    """Per-iteration status for the closed-loop audit trail."""
    iteration: int
    stage: str   # INGEST | GENERATE | VERIFY_STRUCTURAL | VERIFY_SEMANTIC | EXECUTE
    status: str  # PASS | FAIL | CONTINUE
    reason: str
    elapsed_seconds: float
    error_type: Optional[str] = None


@dataclass
class RetrievalResult:
    """A single candidate retrieved from Qdrant."""
    id: str
    score: float
    payload: dict
    content: str
    source_kind: str  # code | doc | review | incident
