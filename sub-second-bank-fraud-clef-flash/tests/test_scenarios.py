"""GUIDE §8: every named scenario yields its expected decision (offline, fake backend)."""

import json

import pytest

from conftest import run
from fraudclef.backends import FakeBackend
from fraudclef.datagen import scenarios
from fraudclef.engine import FraudEngine
from fraudclef.models import ScoringRequest
from fraudclef.policy import PolicyError, load_policy


@pytest.mark.parametrize("scenario", scenarios(), ids=lambda s: s["name"])
def test_scenario(scenario):
    policy = load_policy("policies/retail-eu.yaml", scenario.get("policy_overrides"))
    backend = FakeBackend(fail=scenario.get("simulate_backend_failure", False))
    engine = FraudEngine(policy, backend)
    d = run(engine.score(ScoringRequest.model_validate(scenario["request"]), routing=scenario.get("routing")))
    assert d.decision in scenario["expected"], d.model_dump_json(indent=2)
    if scenario.get("policy_overrides", {}).get("governance", {}).get("mode") == "shadow":
        assert d.enforced is False


def test_cascade_skips_model_for_habitual_spend():
    s = next(s for s in scenarios() if s["name"] == "01_usual_groceries")
    backend = FakeBackend()
    d = run(FraudEngine(load_policy("policies/retail-eu.yaml"), backend).score(ScoringRequest.model_validate(s["request"])))
    assert d.decided_by == "prescore" and backend.calls == 0


def test_always_routing_calls_model():
    s = next(s for s in scenarios() if s["name"] == "01_usual_groceries")
    backend = FakeBackend()
    d = run(FraudEngine(load_policy("policies/retail-eu.yaml"), backend).score(ScoringRequest.model_validate(s["request"]), routing="always"))
    assert d.decided_by == "model" and backend.calls == 1


def test_model_state_is_pseudonymised():
    """No raw IBAN, beneficiary name, device id or merchant name may leave the process."""
    s = next(s for s in scenarios() if s["name"] == "09_vulnerable_unusual_transfer")
    req = ScoringRequest.model_validate(s["request"])
    engine = FraudEngine(load_policy("policies/retail-eu.yaml"), FakeBackend())
    from fraudclef.features import compute_features

    state = json.dumps(engine._model_state(req, compute_features(req, engine.policy.lists, set())))
    for raw in [req.candidate.beneficiary.iban, req.candidate.beneficiary.name, req.candidate.device_id,
                "ESSELUNGA", "Giulia Rossi", "IT60X0542811101000000123456"]:
        assert raw not in state
    assert "h:" in state


def test_timeout_triggers_fail_mode():
    s = next(s for s in scenarios() if s["name"] == "14_backend_down_instant")
    policy = load_policy("policies/retail-eu.yaml", {"model": {"timeout_ms": {"sepa_instant": 500}}})
    d = run(FraudEngine(policy, FakeBackend(delay_s=2.0)).score(ScoringRequest.model_validate(s["request"])))
    assert d.decided_by == "fail_mode" and d.decision == "step_up"
    assert d.latency_ms["total"] < 1000


def test_open_circuit_skips_backend_and_applies_fail_mode():
    s = next(s for s in scenarios() if s["name"] == "02_amount_spike_ecommerce")
    backend = FakeBackend(fail=True)
    engine = FraudEngine(load_policy("policies/retail-eu.yaml"), backend)
    req = ScoringRequest.model_validate(s["request"])
    min_calls = engine.policy.model.circuit_breaker.min_calls
    for _ in range(min_calls):
        run(engine.score(req))
    assert engine.router.breaker.is_open and backend.calls == min_calls

    d = run(engine.score(req))
    assert backend.calls == min_calls  # not called while the circuit is open
    assert d.decided_by == "fail_mode" and d.decision == "step_up"  # card_not_present fail mode
    assert "circuit open" in d.reasons[0].detail


def test_external_backend_forbidden_by_privacy_policy():
    policy = load_policy("policies/retail-eu.yaml", {"privacy": {"allow_external_backend": False}})

    class Remote(FakeBackend):
        name = "regolo"

    with pytest.raises(ValueError, match="forbids sending data"):
        FraudEngine(policy, Remote())


def test_remote_payment_without_sca_needs_exemption():
    """Low-risk e-commerce without SCA: TRA exemption under the threshold, step-up above it."""
    base = next(s for s in scenarios() if s["name"] == "12_recurring_subscription")
    policy = load_policy("policies/retail-eu.yaml")
    small = json.loads(json.dumps(base["request"]))
    small["candidate"].update(recurring=False, authentication="none", amount=12.0)
    d = run(FraudEngine(policy, FakeBackend()).score(ScoringRequest.model_validate(small)))
    assert d.decision == "approve" and d.sca_exemption == "tra"

    big = json.loads(json.dumps(small))
    big["candidate"]["amount"] = 300.0  # above the EUR 250 TRA tier allowed at 5 bps
    d = run(FraudEngine(policy, FakeBackend()).score(ScoringRequest.model_validate(big)))
    assert d.decision != "approve"


@pytest.mark.parametrize("n", [3, 10, 30])
def test_history_window_follows_the_policy(n):
    policy = load_policy("policies/retail-eu.yaml", {"history": {"payments": n}})
    item = next(s for s in scenarios() if s["name"] == "02_amount_spike_ecommerce")
    req = ScoringRequest.model_validate(item["request"])
    seen = {}

    class Spy(FakeBackend):
        async def decide(self, state, questions, timeout_s):
            seen["state"] = state
            return await super().decide(state, questions, timeout_s)

    engine = FraudEngine(policy, Spy())
    d = run(engine.score(req, routing="always"))
    assert d.history_used == n and d.history_available == 30
    assert len(seen["state"]["history"]) == n
    assert seen["state"]["features"]["history_len"] == n


def test_history_window_default_and_bounds():
    assert load_policy("policies/retail-eu.yaml").history.payments == 10
    for bad in (0, 51):
        with pytest.raises(PolicyError):
            load_policy("policies/retail-eu.yaml", {"history": {"payments": bad}})
