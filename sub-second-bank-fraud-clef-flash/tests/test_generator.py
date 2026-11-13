"""Generated datasets: mix allocation, conversion of the model's compact output, repair and
failure handling, saving, and use from the console. The chat model is simulated: no network."""

import time

import pytest
from fastapi.testclient import TestClient

from conftest import run
from fraudclef import benchmark, generator
from fraudclef.models import ScoringRequest
from fraudclef.web import app as web


def compact(kind: str = "habitual", bad: bool = False) -> dict:
    hist = [
        {"minutes_ago": 60 * 24 * d, "amount": 40 + d, "channel": "card_present", "merchant": "CONAD", "mcc": "5411", "city": "rome"}
        for d in (20, 12, 5)
    ] + [
        {"minutes_ago": 60 * 24 * 9, "amount": 650, "channel": "sepa_credit_transfer",
         "beneficiary": {"name": "Anna Bianchi", "iban_country": "IT", "vop": "match"}, "device": "home", "authentication": "sca"},
        {"minutes_ago": 60 * 24 * 15, "amount": 70, "channel": "sepa_direct_debit", "recurring": True,
         "creditor": {"name": "ACEA Energia", "mandate_signed_days_ago": 400}},
    ]
    cand = {"amount": 1800, "channel": "sepa_instant", "device": "new", "ip_country": "LT", "authentication": "sca",
            "beneficiary": {"name": "Anna Bianchi", "iban_country": "IT", "vop": "no_match"}}
    if bad:
        cand = {"amount": -5, "channel": "teleport"}
    return {"description": f"A {kind} case", "customer": {"segment": "retail", "account_age_days": 800},
            "profile_change": {"field": "phone", "hours_ago": 5}, "history": hist, "candidate": cand}


def test_allocation_is_exact_and_follows_the_mix():
    plan = generator.allocate({"habitual": 50, "card_testing": 30, "atm_cashout": 20}, 7)
    assert len(plan) == 7
    counts = {k: plan.count(k) for k in set(plan)}
    assert counts == {"habitual": 4, "card_testing": 2, "atm_cashout": 1}  # 3.5, 2.1, 1.4 → largest remainders
    assert generator.allocate({"habitual": 1, "card_testing": 0}, 5) == ["habitual"] * 5
    with pytest.raises(generator.GenerationError):
        generator.allocate({"habitual": 0}, 5)
    with pytest.raises(generator.GenerationError):
        generator.allocate({"teleport": 10}, 5)


def test_compact_output_becomes_a_valid_request():
    req = generator.to_request(compact(), "g001-001", "rome")
    parsed = ScoringRequest.model_validate(req)
    assert len(parsed.history) == 5 and parsed.candidate.channel == "sepa_instant"
    # Same beneficiary name → same IBAN, so "known beneficiary" works; the new device differs from home.
    transfer = next(t for t in parsed.history if t.beneficiary)
    assert transfer.beneficiary.iban == parsed.candidate.beneficiary.iban
    assert parsed.candidate.device_id != transfer.device_id
    assert parsed.customer.recent_profile_changes and parsed.customer.home_country == "IT"
    with pytest.raises(Exception):
        generator.to_request(compact(bad=True), "g001-002", "rome")


@pytest.fixture
def fake_regolo(monkeypatch, tmp_path):
    calls = {"n": 0}

    async def models():
        return [{"id": "writer", "input": 1e-7, "output": 4e-7, "max_input_tokens": 30000}]

    async def chat_json(model, messages, timeout_s=120):
        calls["n"] += 1
        user = messages[1]["content"]
        broken = "Card testing" in user and len(messages) == 2  # first answer wrong, the correction is fine
        hopeless = "ATM cash-out" in user
        return compact(bad=broken or hopeless), {"prompt_tokens": 1000, "completion_tokens": 500}

    monkeypatch.setattr(generator, "chat_models", models)
    monkeypatch.setattr(generator, "chat_json", chat_json)
    monkeypatch.setattr(generator, "GENERATED_DIR", tmp_path / "generated")
    return calls


def test_generate_set_repairs_once_and_counts_failures(fake_regolo):
    meta = run(generator.generate_set("mix-a", "writer", {"habitual": 50, "card_testing": 25, "atm_cashout": 25}, 4, history=5))
    assert meta["counts"] == {"habitual": 2, "card_testing": 1, "atm_cashout": 1}
    assert meta["generated"] == 3 and meta["repaired"] == 1 and len(meta["failed"]) == 1
    # 2 habitual calls + 2 card testing (one repair) + 2 ATM (repair fails too) = 6 calls
    assert fake_regolo["n"] == 6 and meta["input_tokens"] == 6000 and meta["output_tokens"] == 3000
    assert meta["cost_usd"] == round(6000 * 1e-7 + 3000 * 4e-7, 5)
    items = __import__("json").loads((generator.GENERATED_DIR / "mix-a.json").read_text())
    kinds = {i["type"]: i for i in items}
    assert kinds["card_testing"]["label"] == "fraud" and kinds["card_testing"]["expected"] == generator.FRAUD_EXPECTED
    assert kinds["habitual"]["label"] == "legit" and [m["name"] for m in generator.list_sets()] == ["mix-a"]


@pytest.fixture
def client(tmp_path, monkeypatch, fake_regolo):
    monkeypatch.setenv("FRAUDCLEF_UI_BACKEND", "fake")
    monkeypatch.setattr(web, "AUDIT_LOG", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(benchmark, "RUNS_DIR", tmp_path / "runs")
    with TestClient(web.app) as c:
        yield c


def _wait(client, path):
    for _ in range(200):
        j = client.get(path).json()
        if j["status"] != "running":
            return j
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_console_generates_and_uses_a_set(client):
    body = {"name": "demo", "model": "writer", "n": 4, "history": 5, "mix": {"habitual": 50, "account_takeover": 50}}
    est = client.post("/api/generate/estimate", json=body).json()
    assert est["counts"] == {"habitual": 2, "account_takeover": 2} and est["usd"] > 0
    j = _wait(client, f"/api/generate/jobs/{client.post('/api/generate', json=body).json()['job']}")
    assert j["status"] == "done" and j["result"]["generated"] == 4
    assert client.post("/api/generate", json=body).status_code == 409  # name taken

    ids = [d["id"] for d in client.get("/api/datasets").json()]
    assert "generated:demo" in ids
    rows = client.get("/api/scenarios", params={"dataset": "generated:demo"}).json()
    assert len(rows) == 4 and {r["label"] for r in rows} == {"legit", "fraud"}
    r = client.post("/api/score", json={"dataset": "generated:demo", "scenario": rows[0]["name"]}).json()
    assert r["pass"] in (True, False) and r["decision"]["history_used"] == 5

    bench = client.post("/api/bench", json={"dataset": "generated:demo", "modes": ["cascade"], "n": 5}).json()
    rep = _wait(client, f"/api/bench/jobs/{bench['job']}")
    assert rep["status"] == "done" and rep["report"]["n"] == 4 and rep["report"]["dataset"].startswith("generated:demo")


def test_dataset_names_are_confined(client):
    assert client.get("/api/scenarios", params={"dataset": "generated:../../.env"}).status_code == 422
    assert client.get("/api/scenarios", params={"dataset": "generated:nope"}).status_code == 404
    bad = {"name": "../x", "model": "writer", "n": 2, "mix": {"habitual": 1}}
    assert client.post("/api/generate", json=bad).status_code == 422
    assert client.post("/api/generate/estimate", json={**bad, "name": "ok", "model": "missing"}).status_code == 422
