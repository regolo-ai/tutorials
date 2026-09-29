"""
Domain Models and Pydantic Schemas for Insurance Claims & Policy Triage.
Defines typed interfaces for taxonomy options, structured case briefs,
and end-to-end triage assessment results.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class Option(BaseModel):
    """Represents a declared candidate route in the insurance taxonomy."""
    id: str = Field(description="Unique machine-readable identifier (e.g. 'claims_intake').")
    description: str = Field(description="Semantic description explaining the scope of this category.")


class CaseBrief(BaseModel):
    """
    Structured internal case brief prepared for human insurance handlers.
    Constrained by policy to prevent autonomous coverage determinations.
    """
    summary: str = Field(
        description="Objective 1-2 sentence factual summary of the customer's communication."
    )
    information_to_check: List[str] = Field(
        default_factory=list,
        description="Specific factual claims, policy numbers, or attachments requiring operator verification."
    )
    review_flags: List[str] = Field(
        default_factory=list,
        description="Operational indicators such as active hazard escalation, legal risk, or coverage limits."
    )
    suggested_next_action: str = Field(
        description="Recommended internal procedural step for the human operator."
    )

    @field_validator("suggested_next_action", mode="before")
    @classmethod
    def normalize_suggested_action(cls, v: Any) -> str:
        """Handles cases where generative models return a bulleted list instead of a string."""
        if isinstance(v, list):
            return " ".join(str(item) for item in v)
        return str(v)


class TriageOutput(BaseModel):
    """
    Complete output contract representing the three decoupled triage signals:
    1. Category (semantic intent)
    2. Complexity (cognitive processing demand)
    3. Priority (deterministic operational urgency)
    """
    status: str = Field(description="Operational status: 'awaiting_operator_review' or 'manual_review'.")
    category: Optional[str] = Field(default=None, description="Assigned taxonomy category ID.")
    complexity: Optional[str] = Field(default=None, description="Assigned complexity grade ('easy', 'medium', 'hard').")
    priority: str = Field(default="standard", description="Deterministic business priority ('high' or 'standard').")
    confidence: Optional[float] = Field(default=None, description="Statistical model confidence score (0.0 to 1.0).")
    p_abstain: Optional[float] = Field(default=None, description="Probability of abstention/out-of-scope intent.")
    brief: Optional[CaseBrief] = Field(default=None, description="Synthesized case brief (None if gated to manual review).")
    reason: Optional[str] = Field(default=None, description="Detailed reason code if routed to manual review.")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="Per-class probability distribution and diagnostic metrics.")
