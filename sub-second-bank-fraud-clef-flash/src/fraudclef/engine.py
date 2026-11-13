"""Scoring pipeline: features → hard rules → pre-score → (Clef-Flash) → decision → SCA → audit."""

from __future__ import annotations

import time
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any

from .audit import AuditLog, canonical, sha256
from .backends import BackendError, BackendRouter, DecisionBackend, ModelResult
from .features import compute_features, normalise, summarise_history
from .models import SCA_REMOTE_CHANNELS, SEVERITY, Decision, Reason, ScoringRequest, Transaction
from .policy import Policy
from .privacy import Pseudonymizer
from .rules import ExpressionEvaluator, RuleError


# What started a decision (console scenario, benchmark run, CLI), written into its audit record.
# A context variable, so concurrent score() calls in one engine each keep their own.
_audit_context: ContextVar[dict | None] = ContextVar("audit_context", default=None)
# The request as received, before the history window: its hash goes into the audit record.
_received: ContextVar[ScoringRequest | None] = ContextVar("received_request", default=None)


def build_rule_context(policy: Policy, req: ScoringRequest, features: dict) -> dict[str, Any]:
    customer = req.customer.model_dump(mode="json")
    # Limits are keyed by segment; vulnerable customers get their own, stricter row.
    customer["limit_segment"] = "vulnerable" if req.customer.vulnerable else req.customer.segment
    return {
        "candidate": req.candidate.model_dump(mode="json"),
        "customer": customer,
        "features": features,
        "lists": policy.lists,
        "limits": policy.limits,
    }


def sample_request() -> ScoringRequest:
    """Minimal valid request used to dry-run policy expressions at load time."""
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    tx = Transaction(transaction_id="h1", timestamp=now - timedelta(days=1), amount=10, channel="card_present")
    cand = Transaction(transaction_id="c1", timestamp=now, amount=20, channel="card_present")
    return ScoringRequest(customer={"id": "sample"}, history=[tx], candidate=cand)


class FraudEngine:
    def __init__(
        self,
        policy: Policy,
        backend: DecisionBackend | None,
        audit: AuditLog | None = None,
        pseudonymizer: Pseudonymizer | None = None,
    ):
        if backend and backend.name == "regolo" and not policy.privacy.allow_external_backend:
            raise ValueError("policy forbids sending data to an external backend "
                             "(privacy.allow_external_backend: false); use routing.mode: never")
        self.policy = policy
        self.router = BackendRouter(backend, policy.model.circuit_breaker) if backend else None
        self.audit = audit
        self.pseudo = pseudonymizer or Pseudonymizer()
        self.rules = ExpressionEvaluator()

    async def aclose(self) -> None:
        if self.router:
            await self.router.aclose()

    # ── public API ────────────────────────────────────────────────────────
    async def score(self, req: ScoringRequest, routing: str | None = None, context: dict | None = None) -> Decision:
        """`context` describes what triggered the decision; it goes into the audit record only."""
        token, token_req = _audit_context.set(context), _received.set(req)
        try:
            return await self._score(self._window(req), routing)
        finally:
            _audit_context.reset(token)
            _received.reset(token_req)

    def _window(self, req: ScoringRequest) -> ScoringRequest:
        """Keep the policy's number of most recent payments before the candidate."""
        before = [t for t in req.history if t.timestamp < req.candidate.timestamp]
        return req.model_copy(update={"history": before[-self.policy.history.payments:]})

    async def _score(self, req: ScoringRequest, routing: str | None) -> Decision:
        p = self.policy
        c = req.candidate
        lat: dict[str, float] = {}
        t_start = time.perf_counter()
        reasons: list[Reason] = []

        t = time.perf_counter()
        features = compute_features(req, p.lists, set(p.mule_ibans))
        lat["features"] = _ms(t)
        ctx = build_rule_context(p, req, features)

        # Level 2: hard rules
        t = time.perf_counter()
        rule_hit = None
        for rule in p.hard_rules:
            try:
                if self.rules.evaluate(rule.when, ctx):
                    rule_hit = rule
                    break
            except RuleError as e:
                # Fail closed: a rule that cannot be evaluated must not let the payment through silently.
                reasons.append(Reason(source="rule", id=f"{rule.id}:error", detail=str(e)))
                return await self._finish(req, features, "step_up", 1.0, 0.0, None, "rule", reasons, None, lat, t_start)
        lat["rules"] = _ms(t)

        # Level 3: pre-score (also computed after a rule hit, for SCA and analytics)
        t = time.perf_counter()
        prescore, contributions = self._prescore(features)
        lat["prescore"] = _ms(t)
        reasons += [Reason(source="prescore", id=k, value=round(v, 3)) for k, v in contributions[:3] if v > 0]

        if rule_hit:
            reasons.insert(0, Reason(source="rule", id=rule_hit.id, detail=rule_hit.reason))
            return await self._finish(req, features, rule_hit.decision, prescore, prescore, None, "rule", reasons, None, lat, t_start)

        mode = routing or p.routing.mode
        forced = self._model_forced(c)
        if mode == "never" or (mode == "cascade" and not forced):
            if mode == "never" or prescore < p.routing.approve_if_prescore_below:
                action = self._threshold_action(prescore, req) if mode == "never" else "approve"
                return await self._finish(req, features, action, prescore, prescore, None, "prescore", reasons, None, lat, t_start)
            if prescore > p.routing.block_if_prescore_above:
                return await self._finish(req, features, "block", prescore, prescore, None, "prescore", reasons, None, lat, t_start)

        # Level 4: Clef-Flash
        if self.router is None:
            raise RuntimeError("routing requires a model but no backend is configured")
        state = self._model_state(req, features)
        questions = {qid: q.to_systemone() for qid, q in p.questions.items()}
        t = time.perf_counter()
        try:
            result = await self.router.decide(state, questions, p.model.timeout_for(c.channel))
        except BackendError as e:
            lat["model"] = _ms(t)
            return await self._fail_mode(req, features, prescore, reasons, str(e), lat, t_start, state)
        lat["model"] = _ms(t)

        model_risk, answers_ctx, model_reasons = self._model_risk(result)
        reasons += model_reasons
        w = p.decision.combine
        risk = w.prescore * prescore + w.model * model_risk
        action = self._threshold_action(risk, req)

        # Overrides: first matching wins.
        ctx["answers"] = answers_ctx
        for o in p.decision.overrides:
            try:
                if self.rules.evaluate(o.when, ctx):
                    action = o.decision
                    reasons.insert(0, Reason(source="override", id=o.when, detail=o.reason, value=o.decision))
                    break
            except RuleError as e:
                reasons.append(Reason(source="override", id="error", detail=str(e)))
                action = _max_action(action, "step_up")
        return await self._finish(req, features, action, risk, prescore, model_risk, "model", reasons, result, lat, t_start, state)

    # ── levels ────────────────────────────────────────────────────────────
    def _prescore(self, features: dict) -> tuple[float, list[tuple[str, float]]]:
        contrib = [(name, w * normalise(name, features[name])) for name, w in self.policy.prescore.weights.items()]
        contrib.sort(key=lambda kv: kv[1], reverse=True)
        return min(sum(v for _, v in contrib), 1.0), contrib

    def _model_forced(self, c: Transaction) -> bool:
        rule = self.policy.routing.always_call_model_if
        return (rule.amount_at_least is not None and c.amount >= rule.amount_at_least) or c.channel in rule.channels

    def _thresholds(self, req: ScoringRequest):
        th = self.policy.decision.thresholds
        if req.customer.vulnerable and "vulnerable" in th:
            return th["vulnerable"]
        return th.get(req.customer.segment, th["default"])

    def _threshold_action(self, risk: float, req: ScoringRequest) -> str:
        th = self._thresholds(req)
        if risk >= th.block:
            return "block"
        if risk >= th.hold:
            return "hold"
        if risk >= th.step_up:
            return "step_up"
        return "approve"

    def _model_risk(self, result: ModelResult) -> tuple[float, dict[str, Any], list[Reason]]:
        total = 0.0
        ctx: dict[str, Any] = {}
        reasons: list[Reason] = []
        for qid, q in self.policy.questions.items():
            a = result.answers[qid]
            if q.type == "noul":
                r = float(a["noul"])
                ctx[qid] = r
                value = round(r, 4)
            elif q.type == "choice":
                probs = a["probabilities"]
                r = sum(float(probs[o]) * q.risk_by_option[o] for o in q.risk_by_option)
                ctx[qid], ctx[f"{qid}_confidence"] = a["choice"], float(a["confidence"])
                value = a["choice"]
            else:  # score: expected level scaled to [0, 1]
                n = len(q.criteria)
                r = float(a["score"]) / (n - 1)
                ctx[qid] = float(a["score"])
                value = round(float(a["score"]), 3)
            total += q.weight * r
            reasons.append(Reason(source="model", id=qid, value=value, detail=f"risk={r:.3f}"))
        reasons.sort(key=lambda x: float(x.detail.split("=")[1]), reverse=True)
        return min(total, 1.0), ctx, reasons

    async def _fail_mode(self, req, features, prescore, reasons, error, lat, t_start, state) -> Decision:
        fm = self.policy.decision.on_backend_failure
        mode = fm.get(req.candidate.channel, fm["default"])
        action = self._threshold_action(prescore, req) if mode == "use_prescore" else mode
        reasons.insert(0, Reason(source="fail_mode", id=mode, detail=error))
        return await self._finish(req, features, action, prescore, prescore, None, "fail_mode", reasons, None, lat, t_start, state)

    # ── finishing: channel constraints, SCA, shadow mode, audit ───────────
    async def _finish(self, req, features, action, risk, prescore, model_risk, decided_by, reasons,
                      result: ModelResult | None, lat, t_start, state=None) -> Decision:
        p = self.policy
        c = req.candidate

        # Some channels cannot perform an action (no step-up on a direct debit: the payer is not online).
        replacement = p.decision.unavailable_actions.get(c.channel, {}).get(action)
        if replacement:
            reasons.append(Reason(source="channel", id=f"{action}->{replacement}", detail=f"'{action}' not available on {c.channel}"))
            action = replacement

        sca_exemption = None
        if action == "approve" and c.channel in SCA_REMOTE_CHANNELS and c.authentication != "sca":
            sca_exemption = self._sca_exemption(c, risk, features)
            if sca_exemption is None:
                action = "step_up"
                reasons.insert(0, Reason(source="sca", id="sca_required", detail="PSD2: remote payment without SCA and no exemption applies"))

        decision = Decision(
            transaction_id=c.transaction_id,
            decision=action,
            enforced=p.governance.mode == "enforce",
            risk_score=round(risk, 4),
            prescore=round(prescore, 4),
            model_risk=round(model_risk, 4) if model_risk is not None else None,
            decided_by=decided_by,
            reasons=reasons,
            model_answers=result.answers if result else None,
            sca_exemption=sca_exemption,
            backend=result.backend if result else None,
            model=result.model if result else None,
            input_tokens=result.input_tokens if result else None,
            policy=p.ref,
            history_used=len(req.history),
            history_available=len(_received.get().history) if _received.get() else len(req.history),
        )
        lat["total"] = _ms(t_start)
        decision.latency_ms = {k: round(v, 2) for k, v in lat.items()}

        if self.audit:
            await self.audit.append({
                "transaction_id": c.transaction_id,
                "context": _audit_context.get(),
                "input_hash": sha256(canonical((_received.get() or req).model_dump(mode="json"))),
                "policy": p.ref,
                "policy_sha256": p.sha256,
                "features": features,
                "model_state": state if p.audit.log_model_payload == "pseudonymized" else None,
                "model_input_tokens": result.input_tokens if result else None,
                "decision": decision.model_dump(mode="json"),
            })
        return decision

    def _sca_exemption(self, c: Transaction, risk: float, features: dict) -> str | None:
        """PSD2 RTS SCA: recurring (Art. 14) or transaction risk analysis (Art. 18)."""
        if features.get("recurring_matches_known"):
            return "recurring"
        sca = self.policy.sca
        if risk >= sca.exempt_only_if_risk_below:
            return None
        kind = "card_not_present" if c.channel == "card_not_present" else "credit_transfer"
        rate = sca.current_fraud_rate_bps[kind]
        allowed = max((tier.eur for tier in sca.tra_thresholds_eur[kind] if rate <= tier.max_rate_bps), default=0)
        return "tra" if c.amount <= allowed else None

    # ── model payload ─────────────────────────────────────────────────────
    def _model_state(self, req: ScoringRequest, features: dict) -> dict:
        """Compact, pseudonymised state. Only what the questions need leaves the process."""
        pv = self.policy.privacy
        t0 = req.candidate.timestamp

        def compact(tx: Transaction) -> dict:
            d = self.pseudo.apply(tx.model_dump(mode="json", exclude_none=True), pv.pseudonymize, pv.drop_fields_before_model)
            out = {
                "when": _relative(t0 - tx.timestamp) if tx is not req.candidate else "now",
                "local_hour": tx.timestamp.hour,
                "amount": tx.amount,
                "currency": tx.currency,
                "channel": tx.channel,
            }
            for key in ("merchant", "beneficiary", "mandate", "device_id", "ip_country", "recurring", "authentication", "errors"):
                if d.get(key) not in (None, {}, False):
                    out[key] = d[key]
            if tx.location:
                out["country"] = tx.location.country
            return out

        cust = req.customer
        return {
            "task": "Assess whether the candidate payment is fraud against the account holder, "
                    "using the customer's history and the precomputed features.",
            "customer": {
                "segment": cust.segment,
                "vulnerable": cust.vulnerable,
                "account_age_days": cust.account_age_days,
                "home_country": cust.home_country,
                **({"usual_countries": cust.usual_countries} if cust.usual_countries is not None else {}),
                "hours_since_profile_change": features["profile_change_hours"] if features["profile_change_hours"] < 1e5 else None,
            },
            "history_summary": summarise_history(req),
            "history": [compact(t) for t in req.history],  # already cut to policy.history.payments
            "candidate": compact(req.candidate),
            # Negative signals ("device is known") help the model as much as positive ones; only
            # the "never happened" sentinels are dropped.
            "features": {k: v for k, v in features.items() if not (isinstance(v, float) and v >= 1e5)},
        }


def _relative(delta: timedelta) -> str:
    s = int(delta.total_seconds())
    if s < 3600:
        return f"-{s // 60}m"
    if s < 86400:
        return f"-{s // 3600}h{(s % 3600) // 60:02d}m"
    return f"-{s // 86400}d{(s % 86400) // 3600}h"


def _ms(t: float) -> float:
    return (time.perf_counter() - t) * 1000


def _max_action(a: str, b: str) -> str:
    return a if SEVERITY[a] >= SEVERITY[b] else b
