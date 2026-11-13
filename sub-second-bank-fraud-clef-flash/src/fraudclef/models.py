"""Input and output schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Channel = Literal[
    "card_present",
    "card_not_present",
    "atm",
    "sepa_instant",
    "sepa_credit_transfer",
    "sepa_direct_debit",
]
Action = Literal["approve", "step_up", "hold", "block"]
VopResult = Literal["match", "close_match", "no_match", "unavailable"]
# Why an attempt was declined, as card processors report it. Only past attempts carry errors:
# the candidate is being decided, so it has none yet.
AttemptError = Literal["bad_pin", "bad_cvv", "bad_card_number", "bad_expiration", "bad_zipcode",
                       "insufficient_balance", "technical_glitch"]

# Severity order, used when comparing or escalating decisions.
SEVERITY: dict[str, int] = {"approve": 0, "step_up": 1, "hold": 2, "block": 3}

PHYSICAL_CHANNELS = {"card_present", "atm"}
TRANSFER_CHANNELS = {"sepa_instant", "sepa_credit_transfer"}
# Payer-initiated remote payments: PSD2 SCA applies unless an exemption is used.
SCA_REMOTE_CHANNELS = {"card_not_present", "sepa_instant", "sepa_credit_transfer"}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Merchant(_Strict):
    name: str | None = None
    mcc: str | None = None
    country: str | None = None


class Location(_Strict):
    lat: float
    lon: float
    country: str | None = None


class Beneficiary(_Strict):
    iban: str
    name: str | None = None
    vop_result: VopResult | None = None

    @field_validator("iban")
    @classmethod
    def _normalise_iban(cls, v: str) -> str:
        return v.replace(" ", "").upper()

    @property
    def country(self) -> str:
        return self.iban[:2]


class Mandate(_Strict):
    creditor_id: str
    mandate_id: str
    signed_at: datetime


class Transaction(_Strict):
    transaction_id: str
    timestamp: datetime
    amount: float = Field(gt=0)
    currency: str = "EUR"
    channel: Channel
    merchant: Merchant | None = None
    location: Location | None = None
    device_id: str | None = None
    ip_country: str | None = None
    beneficiary: Beneficiary | None = None
    mandate: Mandate | None = None
    recurring: bool = False
    authentication: Literal["sca", "none", "exemption"] = "none"
    description: str | None = None
    errors: list[AttemptError] = Field(default_factory=list)  # declined attempt, and why

    @field_validator("timestamp")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must include a timezone offset")
        return v


class ProfileChange(_Strict):
    field: str
    at: datetime


class Customer(_Strict):
    id: str
    segment: Literal["retail", "business"] = "retail"
    vulnerable: bool = False
    account_age_days: int = 0
    home_country: str = "IT"
    # From the bank's customer profile, not from `history`: countries paid in over a longer period
    # (TabFormer samples: 90 days ending 30 days before the payment, so a fraud burst is not counted).
    usual_countries: list[str] | None = None
    recent_profile_changes: list[ProfileChange] = Field(default_factory=list)


class ScoringRequest(_Strict):
    customer: Customer
    history: list[Transaction] = Field(max_length=50)
    candidate: Transaction

    @field_validator("history")
    @classmethod
    def _sort_history(cls, v: list[Transaction]) -> list[Transaction]:
        return sorted(v, key=lambda t: t.timestamp)


class Reason(BaseModel):
    source: Literal["rule", "prescore", "model", "sca", "fail_mode", "override", "channel"]
    id: str
    detail: str | None = None
    value: Any = None


class Decision(BaseModel):
    transaction_id: str
    decision: Action
    enforced: bool = True
    risk_score: float
    prescore: float
    model_risk: float | None = None
    decided_by: Literal["rule", "prescore", "model", "fail_mode"]
    reasons: list[Reason] = Field(default_factory=list)
    model_answers: dict[str, Any] | None = None
    sca_exemption: str | None = None
    backend: str | None = None
    model: str | None = None
    input_tokens: int | None = None   # billed input tokens of the model call (Regolo usage)
    history_used: int = 0             # past payments read (policy history.payments, or fewer if not available)
    history_available: int = 0        # past payments received in the request
    policy: str
    latency_ms: dict[str, float] = Field(default_factory=dict)
