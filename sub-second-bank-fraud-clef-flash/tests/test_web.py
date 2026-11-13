"""Console API on the fake backend: no network, temporary audit log and benchmark folder."""

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fraudclef import benchmark
from fraudclef.web import app as web


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FRAUDCLEF_UI_BACKEND", "fake")
    monkeypatch.setattr(web, "AUDIT_LOG", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(benchmark, "RUNS_DIR", tmp_path / "runs")
    # Editable copies: the editor tests write policies and .env.
    shutil.copytree("policies", tmp_path / "policies")
    shutil.copytree("lists", tmp_path / "lists")
    monkeypatch.setattr(web, "POLICY_DIR", tmp_path / "policies")
    monkeypatch.setattr(web, "ENV_FILE", tmp_path / ".env")

    async def offline_status():
        return {"key_present": False, "reachable": False, "model_listed": False}

    monkeypatch.setattr(web, "_regolo_status", offline_status)
    with TestClient(web.app) as c:
        yield c


def test_status_never_exposes_the_key(client, monkeypatch):
    monkeypatch.setenv("REGOLO_API_KEY", "sk-secret-value")
    s = client.get("/api/status").json()
    assert s["backend"] == "fake"
    assert all(p["ok"] for p in s["policies"])
    assert "sk-secret-value" not in client.get("/api/status").text


def test_score_scenario_and_audit(client):
    r = client.post("/api/score", json={"scenario": "06_fake_bank_operator"}).json()
    assert r["decision"]["decision"] == "hold" and r["pass"] is True
    r = client.post("/api/score", json={"scenario": "15_shadow_mode", "batch": "scenarios_1"}).json()
    assert r["decision"]["enforced"] is False
    audit = client.get("/api/audit").json()
    assert audit["verify"]["ok"] and audit["verify"]["records"] == 2
    # Each record says what started it, and runs are grouped.
    rows = {r["scenario"]: r for r in audit["records"]}
    assert rows["06_fake_bank_operator"]["source"] == "console-scenario"
    assert rows["15_shadow_mode"]["group"] == "scenarios_1"
    only = client.get("/api/audit", params={"group": "scenarios_1"}).json()
    assert [r["scenario"] for r in only["records"]] == ["15_shadow_mode"]
    full = client.get(f"/api/audit/records/{only['records'][0]['line']}").json()
    assert full["context"]["scenario"] == "15_shadow_mode" and "features" in full
    assert client.get("/api/audit/records/99").status_code == 404


def test_score_rejects_unknown_inputs(client):
    assert client.post("/api/score", json={"scenario": "nope"}).status_code == 404
    assert client.post("/api/score", json={"request": {"bad": 1}}).status_code == 422
    assert client.post("/api/score", json={"scenario": "01_usual_groceries", "policy": "../.env"}).status_code == 404


def test_bench_job_runs_and_is_saved(client):
    job = client.post("/api/bench", json={"dataset": "scenarios", "modes": ["always", "cascade"], "concurrency": 2}).json()["job"]
    for _ in range(100):
        j = client.get(f"/api/bench/jobs/{job}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done", j
    rep = j["report"]
    cell = {c["mode"]: c for c in rep["configs"]}
    assert cell["cascade"]["sent_to_model_pct"] < cell["always"]["sent_to_model_pct"]
    runs = client.get("/api/bench/runs").json()
    assert runs[0]["id"] == rep["id"] and client.get(f"/api/bench/runs/{rep['id']}").json()["n"] == rep["n"]
    # Benchmark decisions land in the audit log under the run id, one per payment and mode.
    audit = client.get("/api/audit", params={"group": rep["id"]}).json()
    assert audit["matching"] == rep["n"] * 2 and audit["verify"]["ok"]
    assert {r["mode"] for r in audit["records"]} == {"always", "cascade"}


def test_bench_compares_policies_with_the_set_described(client):
    body = {"dataset": "scenarios", "policies": ["retail-eu", "sepa-instant-dach"], "modes": ["cascade", "never"], "concurrency": 2}
    job = client.post("/api/bench", json=body).json()["job"]
    for _ in range(200):
        j = client.get(f"/api/bench/jobs/{job}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    rep = j["report"]
    assert [(c["policy"], c["mode"]) for c in rep["configs"]] == [
        ("retail-eu", "cascade"), ("retail-eu", "never"), ("sepa-instant-dach", "cascade"), ("sepa-instant-dach", "never")]
    # The set is described next to its results: title, how it was built and its payments by type.
    meta = rep["dataset_meta"]
    assert meta["title"] == "European fraud & compliance reference suite" and meta["n"] == rep["n"] == 24
    assert meta["types"]["impersonation_scam"] >= 5 and sum(meta["types"].values()) == 24
    # Per type: how many were stopped, in how long and at what cost.
    t = rep["configs"][0]["by_type"]["card_testing"]
    assert t == {"label": "fraud", "n": 1, "stopped": 1, "median_ms": t["median_ms"], "cost_usd": 0.0}
    runs = client.get("/api/bench/runs").json()
    assert runs[0]["policies"] == ["retail-eu", "sepa-instant-dach"] and runs[0]["dataset_title"] == meta["title"]
    audit = client.get("/api/audit", params={"group": rep["id"]}).json()
    assert audit["matching"] == 24 * 4 and len({r["policy"] for r in audit["records"]}) == 2
    assert client.post("/api/bench", json={**body, "policies": ["../.env"]}).status_code == 404


def test_bench_estimate_counts_model_calls_offline(client):
    before = web.AUDIT_LOG.read_text() if web.AUDIT_LOG.exists() else ""
    body = {"dataset": "scenarios", "policies": ["retail-eu", "retail-eu-explainable"], "modes": ["cascade", "always", "never"]}
    est = client.post("/api/bench/estimate", json=body).json()
    calls = {(c["policy"], c["mode"]): c["model_calls"] for c in est["configs"]}
    assert est["n"] == 24 and len(calls) == 6
    assert calls[("retail-eu", "never")] == 0 < calls[("retail-eu", "cascade")] < calls[("retail-eu", "always")] <= 24
    detailed = {c["mode"]: c["tokens_per_call"] for c in est["configs"] if c["policy"] == "retail-eu-explainable"}
    assert detailed["always"] > next(c["tokens_per_call"] for c in est["configs"] if c["policy"] == "retail-eu")
    assert (web.AUDIT_LOG.read_text() if web.AUDIT_LOG.exists() else "") == before  # the dry run writes nothing


def test_bench_rows_explain_each_payment(client):
    job = client.post("/api/bench", json={"dataset": "scenarios", "modes": ["cascade"], "policies": ["retail-eu"]}).json()["job"]
    for _ in range(100):
        j = client.get(f"/api/bench/jobs/{job}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    row = next(r for r in j["report"]["configs"][0]["rows"] if r["name"] == "04_card_testing")
    assert row["channel"] == "card_not_present" and row["pass"] is True and row["reasons"][0]["id"] == "card_testing_burst"
    assert j["events"] and {"description", "decision", "decided_by"} <= set(j["events"][0])


def test_builtin_sets_by_channel(client):
    sets = {d["id"]: d for d in client.get("/api/datasets").json()}
    assert sets["random-ecommerce"]["title"] == "European e-commerce & remote cards"
    rows = client.get("/api/scenarios", params={"dataset": "random-ecommerce"}).json()
    assert rows and {r["channel"] for r in rows} == {"card_not_present"}
    assert sets["random-ecommerce"]["n"] == len(rows) and "stolen_card_online" in sets["random-ecommerce"]["types"]
    sepa = client.get("/api/scenarios", params={"dataset": "sepa-transfers"}).json()
    assert sepa and {r["channel"] for r in sepa} <= {"sepa_instant", "sepa_credit_transfer"}


def test_bench_concurrency_capped(client):
    assert client.post("/api/bench", json={"concurrency": 50}).status_code == 422


def test_policy_validate_save_and_history(client):
    path = web.POLICY_DIR / "retail-eu.yaml"
    text = path.read_text()
    assert client.post("/api/policies/validate", json={"yaml": text, "name": "retail-eu"}).json()["ok"]

    bad = client.post("/api/policies/validate", json={"yaml": "policy_id: [unclosed", "name": "retail-eu"})
    assert bad.status_code == 422 and "line 1" in bad.json()["detail"]
    weights = text + "\nprescore:\n  weights: {amount_zscore: 0.9}\n"
    assert client.post("/api/policies/validate", json={"yaml": weights, "name": "retail-eu"}).status_code == 422

    edited = text + "\n# tuned in the console\n"
    r = client.put("/api/policies/retail-eu", json={"yaml": edited})
    assert r.status_code == 200 and path.read_text() == edited
    assert Path(r.json()["backup"]).read_text() == text
    assert client.put("/api/policies/retail-eu", json={"yaml": weights}).status_code == 422
    assert path.read_text() == edited  # an invalid save changes nothing


def test_policy_save_refused_if_it_breaks_a_child(client):
    child = "extends: retail-eu.yaml\npolicy_id: child\ndecision:\n  thresholds:\n    default: {step_up: 0.5}\n"
    (web.POLICY_DIR / "child.yaml").write_text(child)
    parent = web.POLICY_DIR / "retail-eu.yaml"
    original = parent.read_text()
    # Valid on its own (0.40 < 0.45 < 0.80), but the child's step_up 0.5 would sit above hold.
    edited = original.replace("hold: 0.65", "hold: 0.45")
    assert client.post("/api/policies/validate", json={"yaml": edited, "name": "retail-eu"}).status_code == 200
    r = client.put("/api/policies/retail-eu", json={"yaml": edited})
    assert r.status_code == 422 and "child" in r.json()["detail"]
    assert parent.read_text() == original
    assert not list((web.POLICY_DIR / ".history").glob("retail-eu-*.yaml"))


def test_policy_create_and_confinement(client):
    assert client.post("/api/policies", json={"name": "sme-italy", "base": "retail-eu"}).json()["created"] == "sme-italy"
    names = [p["name"] for p in client.get("/api/status").json()["policies"]]
    assert "sme-italy" in names
    assert client.post("/api/policies", json={"name": "sme-italy"}).status_code == 409
    assert client.post("/api/policies", json={"name": "../evil"}).status_code == 422
    assert client.post("/api/policies", json={"name": "copy", "base": "retail-eu", "copy_content": True}).status_code == 200
    # The editor cannot reach files outside the policy folder.
    escape = client.post("/api/policies/validate", json={"yaml": "extends: ../.env\n", "name": "x"})
    assert escape.status_code == 422 and "same folder" in escape.json()["detail"]
    lists = client.post("/api/policies/validate", json={"yaml": "extends: retail-eu.yaml\nlists:\n  mule_beneficiaries_file: ../../../etc/hosts\n"})
    assert lists.status_code == 422 and "inside the project" in lists.json()["detail"]
    assert client.put("/api/policies/..%2F.env", json={"yaml": "a: 1"}).status_code == 404


def test_writes_refuse_other_origins(client):
    r = client.post("/api/policies", json={"name": "x1"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/settings/regolo-key", content="key=abc", headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 415


def test_api_key_is_checked_saved_and_never_returned(client, monkeypatch):
    web.ENV_FILE.write_text("# comment\nREGOLO_API_KEY=\nFRAUDCLEF_HMAC_KEY=keep-me\n")

    async def accept(key):
        return key == "sk-good-key-123"

    monkeypatch.setattr(web, "_key_accepted", accept)
    monkeypatch.delenv("REGOLO_API_KEY", raising=False)
    r = client.post("/api/settings/regolo-key", json={"key": "sk-wrong-key-123"})
    assert r.status_code == 422 and "REGOLO_API_KEY=\n" in web.ENV_FILE.read_text()
    r = client.post("/api/settings/regolo-key", json={"key": "  sk-good-key-123 "})
    assert r.status_code == 200 and "sk-good" not in r.text
    env = web.ENV_FILE.read_text()
    assert "REGOLO_API_KEY=sk-good-key-123\n" in env and "FRAUDCLEF_HMAC_KEY=keep-me" in env and "# comment" in env
    assert oct(web.ENV_FILE.stat().st_mode & 0o777) == "0o600"
    assert client.post("/api/settings/regolo-key", json={"key": "sk bad key"}).status_code == 422


def test_skipped_model_calls_do_not_skew_latency_or_cost():
    rows = [{"tokens": 2000, "model_ms": 300.0}, {"tokens": 2200, "model_ms": 500.0},
            {"tokens": None, "model_ms": 2400.0},  # timeout
            {"tokens": None, "model_ms": 0.01}, {"tokens": None, "model_ms": 0.01},  # circuit open
            {"tokens": None, "model_ms": None}]  # decided without the model
    mode = {"n": 6, "rows": rows, "latency_by_level_ms": {}}
    out = benchmark.restat({"price": {"usd_per_input_token": 1e-7}, "modes": {"cascade": mode}})["modes"]["cascade"]
    assert out["model_unanswered"] == 3
    assert out["input_tokens_per_call"] == 2100
    assert out["latency_model_ms"]["p50"] in (300.0, 500.0)
    assert out["cost_usd_per_model_call"] == round(2100 * 1e-7, 6)
