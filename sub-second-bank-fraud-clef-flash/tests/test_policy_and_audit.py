import json
import time

import pytest

from conftest import run
from fraudclef.audit import AuditLog, verify
from fraudclef.backends import CircuitBreaker
from fraudclef.features import robust_zscore
from fraudclef.policy import PolicyError, load_policy


def test_policies_load():
    for name in ("retail-eu", "sepa-instant-dach", "retail-eu-explainable", "cards-us", "cards-us-profile"):
        p = load_policy(f"policies/{name}.yaml")
        assert p.sha256 and p.ref.startswith(p.policy_id)


@pytest.mark.parametrize("override, message", [
    ({"governance": {"approved_by": "fraud-strategy-team"}}, "four-eyes"),
    ({"prescore": {"weights": {"amount_zscore": 0.9}}}, "sum to 1"),
    ({"decision": {"thresholds": {"default": {"step_up": 0.7, "hold": 0.5, "block": 0.8}}}}, "thresholds"),
    ({"hard_rules": [{"id": "typo", "when": "features.amount_zscroe > 3", "decision": "block", "reason": "x"}]}, "amount_zscroe"),
    ({"hard_rules": [{"id": "inject", "when": "__import__('os').system('id')", "decision": "block", "reason": "x"}]}, "hard_rules"),
])
def test_invalid_policies_rejected(override, message):
    with pytest.raises(PolicyError, match=message):
        load_policy("policies/retail-eu.yaml", override)


def test_audit_chain_detects_tampering(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for i in range(3):
        run(log.append({"transaction_id": f"t{i}", "decision": {"decision": "approve"}}))
    assert verify(path)[0]

    # A new AuditLog instance continues the same chain.
    run(AuditLog(path).append({"transaction_id": "t3"}))
    assert verify(path) == (True, 4, "hash chain intact")

    lines = path.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["decision"]["decision"] = "block"
    lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")
    ok, n, msg = verify(path)
    assert not ok and n == 2

    path.write_text("\n".join(l for i, l in enumerate(path.read_text().splitlines()) if i != 1) + "\n")
    assert not verify(path)[0]


def test_circuit_breaker_opens_and_recovers():
    cb = CircuitBreaker(failure_ratio=0.5, window_s=30, open_s=0.05, min_calls=4)
    for ok in (True, False, False, False):
        cb.record(ok)
    assert cb.is_open and not cb.allow()
    time.sleep(0.06)
    assert cb.allow()  # half-open
    cb.record(True)
    assert not cb.is_open


def test_robust_zscore_resists_single_outlier():
    habitual = [40, 55, 38, 62, 48, 650, 44, 71, 22, 30]  # one rent payment
    assert robust_zscore(45, habitual) < 1
    assert robust_zscore(1500, habitual) > 20
    assert robust_zscore(10, [10, 10, 10]) == 0  # flat history: no division by zero
