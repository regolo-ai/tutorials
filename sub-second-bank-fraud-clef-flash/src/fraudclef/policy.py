"""Security policy: YAML loading (with `extends`), schema, governance checks and a dry run
of every expression so a broken policy is rejected at startup, never at transaction time."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .features import PRESCORE_NORMALISERS
from .models import Action, Channel

FailMode = Literal["approve", "step_up", "hold", "block", "use_prescore"]


class PolicyError(Exception):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Governance(_Strict):
    author: str
    approved_by: str
    change_ticket: str
    mode: Literal["enforce", "shadow"] = "enforce"

    @model_validator(mode="after")
    def _four_eyes(self):
        if self.author.strip().lower() == self.approved_by.strip().lower():
            raise ValueError("four-eyes principle: approved_by must differ from author")
        return self


class Privacy(_Strict):
    pseudonymize: list[str] = Field(default_factory=list)
    drop_fields_before_model: list[str] = Field(default_factory=list)
    allow_external_backend: bool = False


class HardRule(_Strict):
    id: str
    when: str
    decision: Action
    reason: str


class TraTier(_Strict):
    max_rate_bps: float
    eur: float


class Sca(_Strict):
    current_fraud_rate_bps: dict[Literal["card_not_present", "credit_transfer"], float]
    tra_thresholds_eur: dict[Literal["card_not_present", "credit_transfer"], list[TraTier]]
    exempt_only_if_risk_below: float = Field(ge=0, le=1)


class Prescore(_Strict):
    weights: dict[str, float]


class AlwaysCallModelIf(_Strict):
    amount_at_least: float | None = None
    channels: list[Channel] = Field(default_factory=list)


class Routing(_Strict):
    mode: Literal["cascade", "always", "never"] = "cascade"
    approve_if_prescore_below: float = Field(ge=0, le=1)
    block_if_prescore_above: float = Field(ge=0, le=1)
    always_call_model_if: AlwaysCallModelIf = Field(default_factory=AlwaysCallModelIf)


class CircuitBreakerCfg(_Strict):
    failure_ratio: float = 0.2
    window_s: float = 30
    open_s: float = 60
    min_calls: int = 5


class ModelCfg(_Strict):
    backend: Literal["regolo", "fake"] = "regolo"
    name: str = "clef-flash"
    timeout_ms: dict[str, float]
    circuit_breaker: CircuitBreakerCfg = Field(default_factory=CircuitBreakerCfg)

    def timeout_for(self, channel: str) -> float:
        return self.timeout_ms.get(channel, self.timeout_ms["default"]) / 1000


class Question(_Strict):
    type: Literal["noul", "choice", "score"]
    weight: float = Field(ge=0, le=1)
    instructions: str
    criteria: dict[str, str] | list[str] | None = None
    risk_by_option: dict[str, float] | None = None

    @model_validator(mode="after")
    def _shape(self):
        if self.type == "choice":
            if not isinstance(self.criteria, dict) or len(self.criteria) < 2:
                raise ValueError("choice questions need a criteria mapping with >= 2 options")
            if not self.risk_by_option or set(self.risk_by_option) != set(self.criteria):
                raise ValueError("choice questions need risk_by_option for exactly the criteria options")
        if self.type == "score" and (not isinstance(self.criteria, list) or len(self.criteria) < 2):
            raise ValueError("score questions need a criteria list with >= 2 levels")
        return self

    def to_systemone(self) -> dict[str, Any]:
        q: dict[str, Any] = {"type": self.type, "instructions": self.instructions.strip()}
        if self.criteria is not None:
            q["criteria"] = self.criteria
        return q


class Thresholds(_Strict):
    step_up: float
    hold: float
    block: float

    @model_validator(mode="after")
    def _increasing(self):
        if not (0 <= self.step_up < self.hold < self.block <= 1):
            raise ValueError("thresholds must satisfy 0 <= step_up < hold < block <= 1")
        return self


class Override(_Strict):
    when: str
    decision: Action
    reason: str | None = None


class Combine(_Strict):
    prescore: float
    model: float

    @model_validator(mode="after")
    def _sum(self):
        if abs(self.prescore + self.model - 1) > 1e-6:
            raise ValueError("combine weights must sum to 1")
        return self


class DecisionCfg(_Strict):
    combine: Combine
    thresholds: dict[str, Thresholds]
    overrides: list[Override] = Field(default_factory=list)
    on_backend_failure: dict[str, FailMode]
    # Actions a channel cannot perform, and what to do instead (e.g. no step-up on a direct debit:
    # the payer is not online).
    unavailable_actions: dict[str, dict[Action, Action]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _defaults(self):
        if "default" not in self.thresholds:
            raise ValueError("decision.thresholds needs a 'default' entry")
        if "default" not in self.on_backend_failure:
            raise ValueError("decision.on_backend_failure needs a 'default' entry")
        return self


class History(_Strict):
    # How many of the customer's most recent payments the engine reads: for the features
    # (z-score, velocity, known devices and beneficiaries) and for the state sent to Clef-Flash.
    # More payments give a better baseline but cost more input tokens per model call.
    payments: int = Field(10, ge=1, le=50)


class Audit(_Strict):
    sink: str = "logs/decisions.jsonl"
    hash_chain: bool = True
    retention_days: int = 3650
    log_model_payload: Literal["none", "pseudonymized"] = "pseudonymized"


class Policy(_Strict):
    policy_id: str
    description: str = ""   # one or two sentences shown in the console: what this policy is for
    version: int
    effective_from: date
    governance: Governance
    privacy: Privacy
    history: History = Field(default_factory=History)
    lists: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, dict[str, float]] = Field(default_factory=dict)
    hard_rules: list[HardRule]
    sca: Sca
    prescore: Prescore
    routing: Routing
    model: ModelCfg
    questions: dict[str, Question]
    decision: DecisionCfg
    audit: Audit = Field(default_factory=Audit)

    # Filled by the loader, not part of the YAML schema.
    sha256: str = ""
    mule_ibans: frozenset[str] = frozenset()

    @property
    def ref(self) -> str:
        return f"{self.policy_id}@{self.version} (sha256:{self.sha256[:12]})"

    @model_validator(mode="after")
    def _weights(self):
        _check_sum("prescore.weights", self.prescore.weights.values())
        _check_sum("questions[*].weight", [q.weight for q in self.questions.values()])
        unknown = [f for f in self.prescore.weights if f not in PRESCORE_NORMALISERS and not _is_bool_feature(f)]
        if unknown:
            raise ValueError(f"prescore.weights reference unknown features: {unknown}")
        if self.routing.approve_if_prescore_below >= self.routing.block_if_prescore_above:
            raise ValueError("routing: approve_if_prescore_below must be < block_if_prescore_above")
        return self


def _check_sum(name: str, values) -> None:
    total = sum(values)
    if abs(total - 1) > 1e-6:
        raise ValueError(f"{name} must sum to 1 (got {total:.4f})")


_BOOL_FEATURES = {
    "is_round_amount", "ip_geo_mismatch", "new_merchant", "new_mcc", "high_risk_mcc", "new_country", "unusual_country",
    "high_risk_country", "sanctioned_country", "new_device", "new_beneficiary", "vop_mismatch",
    "first_instant_payment", "beneficiary_in_mule_list", "atm_country_vs_home", "new_creditor",
    "recurring_matches_known", "recent_credential_error", "foreign_merchant",
}


def _is_bool_feature(name: str) -> bool:
    return name in _BOOL_FEATURES


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _parse_yaml(text: str, where: str) -> dict:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        at = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise PolicyError(f"{where}: YAML syntax error{at}: {getattr(e, 'problem', None) or e}") from e
    if not isinstance(data, dict):
        raise PolicyError(f"{where}: a policy must be a YAML mapping (key: value), not {type(data).__name__}")
    return data


def _load_raw(path: Path, seen: set[Path], confine: Path | None = None) -> dict:
    path = path.resolve()
    if path in seen:
        raise PolicyError(f"circular 'extends' at {path}")
    seen.add(path)
    return _resolve(_parse_yaml(path.read_text(), path.name), path.parent, seen, confine)


def _resolve(data: dict, base_dir: Path, seen: set[Path], confine: Path | None) -> dict:
    """Apply `extends` and resolve list files relative to `base_dir`. With `confine` (the editor),
    parents must sit in the same folder and list files under its parent: no reading arbitrary files."""
    parent = data.pop("extends", None)
    if parent:
        target = (base_dir / str(parent)).resolve()
        if confine and target.parent != confine.resolve():
            raise PolicyError(f"extends: '{parent}' must be a policy file in the same folder")
        if not target.exists():
            raise PolicyError(f"extends: '{parent}' not found")
        data = _deep_merge(_load_raw(target, seen, confine), data)
    # Resolve list files relative to the policy that declares them.
    lists = data.get("lists") or {}
    if "mule_beneficiaries_file" in lists and not Path(lists["mule_beneficiaries_file"]).is_absolute():
        target = (base_dir / lists["mule_beneficiaries_file"]).resolve()
        if confine and not target.is_relative_to(confine.resolve().parent):
            raise PolicyError("lists.mule_beneficiaries_file must stay inside the project")
        lists["mule_beneficiaries_file"] = str(target)
    return data


def load_policy(path: str | Path, overrides: dict | None = None) -> Policy:
    return _build(_load_raw(Path(path), set()), str(path), overrides)


def load_policy_text(text: str, base_dir: Path, name: str = "draft") -> Policy:
    """Validate unsaved YAML (the console editor) as if it were saved in `base_dir`."""
    data = _parse_yaml(text, f"{name}.yaml")
    return _build(_resolve(data, base_dir, {(base_dir / f"{name}.yaml").resolve()}, confine=base_dir), f"{name}.yaml")


def _build(raw: dict, where: str, overrides: dict | None = None) -> Policy:
    if overrides:
        raw = _deep_merge(raw, overrides)
    try:
        policy = Policy.model_validate(raw)
    except Exception as e:
        raise PolicyError(f"invalid policy {where}: {e}") from e
    policy.sha256 = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()

    mule_file = policy.lists.get("mule_beneficiaries_file")
    if mule_file:
        try:
            lines = Path(mule_file).read_text().splitlines()
        except OSError as e:
            raise PolicyError(f"lists.mule_beneficiaries_file: cannot read {Path(mule_file).name}") from e
        policy.mule_ibans = frozenset(l.strip().replace(" ", "").upper() for l in lines if l.strip() and not l.startswith("#"))

    _dry_run(policy)
    return policy


def _dry_run(policy: Policy) -> None:
    """Evaluate every expression against a synthetic context, so typos fail at load time."""
    from .engine import build_rule_context, sample_request  # local import: avoid a cycle
    from .features import compute_features
    from .rules import ExpressionEvaluator, RuleError

    req = sample_request()
    features = compute_features(req, policy.lists, set(policy.mule_ibans))
    ctx = build_rule_context(policy, req, features)
    ctx["answers"] = _sample_answers(policy)
    ev = ExpressionEvaluator()
    for expr, where in [(r.when, f"hard_rules[{r.id}]") for r in policy.hard_rules] + [
        (o.when, f"decision.overrides[{i}]") for i, o in enumerate(policy.decision.overrides)
    ]:
        try:
            ev.evaluate(expr, ctx)
        except RuleError as e:
            raise PolicyError(f"{where}: {e}") from e


def _sample_answers(policy: Policy) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for qid, q in policy.questions.items():
        if q.type == "choice":
            out[qid] = next(iter(q.criteria))
            out[f"{qid}_confidence"] = 0.5
        else:
            out[qid] = 0.5
    return out
