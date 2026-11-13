"""TabFormer sample: one fraud per user, history before the candidate, mapping of countries and channels."""

import time
import warnings

import pytest
from fastapi.testclient import TestClient

from fraudclef import benchmark, generator, tabformer
from fraudclef.features import compute_features
from fraudclef.models import ScoringRequest
from fraudclef.web import app as web

HEADER = "User,Card,Year,Month,Day,Time,Amount,Use Chip,Merchant Name,Merchant City,Merchant State,Zip,MCC,Errors?,Is Fraud?\n"


def row(user, day, time, amount, chip="Chip Transaction", state="CA", fraud="No", mcc="5411", errors="", month=3):
    city = "ONLINE" if chip == "Online Transaction" else "Rome" if state == "Italy" else "La Verne"
    errors = f'"{errors}"' if "," in errors else errors
    return f"{user},0,2019,{month},{day},{time},${amount},{chip},123{user},{city},{state},91750.0,{mcc},{errors},{fraud}\n"


def test_sample_keeps_history_before_the_candidate(tmp_path):
    lines = [row(0, d, "10:00", 20 + d) for d in range(1, 8)] + [row(0, 9, "10:40", 5, errors="Bad PIN,")]
    lines += [row(0, 9, "11:00", 900, state="Italy", fraud="Yes", errors="Bad CVV,")]
    lines += [row(1, d, "09:30", 15) for d in range(1, 6)] + [row(1, 6, "12:00", 30, chip="Online Transaction", state="")]
    lines += [row(1, 7, "12:00", "-30.00")]  # a refund: never a candidate, never in history
    csv = tmp_path / "t.csv"
    csv.write_text(HEADER + "".join(lines))
    items, meta = tabformer.build_sample(csv, n_fraud=5, n_legit=50)
    assert meta["period_fraud"] == 1 and meta["fraud"] == 1 and meta["legit"] == 14
    fraud = next(i for i in items if i["label"] == "fraud")
    req = ScoringRequest.model_validate(fraud["request"])
    assert req.candidate.merchant.country == "IT" and req.candidate.channel == "card_present"
    assert len(req.history) == 8 and all(t.timestamp < req.candidate.timestamp for t in req.history)
    online = next(i for i in items if i["request"]["candidate"]["channel"] == "card_not_present")
    assert online["request"]["candidate"]["authentication"] == "sca" and online["request"]["candidate"]["merchant"]["country"] is None
    assert all(i["request"]["candidate"]["amount"] > 0 for i in items)
    # Declined attempts stay on past payments; the candidate's own outcome is not known yet.
    assert req.history[-1].errors == ["bad_pin"] and req.candidate.errors == []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = compute_features(req, {}, set())
    assert f["credential_errors_24h"] == 1 and f["recent_credential_error"] and f["foreign_merchant"]


def test_usual_countries_look_before_a_fraud_burst(tmp_path):
    # User 0 went to Italy in January; user 1 never left the US before a burst in the UK on 1-2 March.
    lines = [row(0, 10, "10:00", 80, state="Italy", month=1)] + [row(0, d, "10:00", 20) for d in range(1, 8)]
    lines += [row(0, 9, "11:00", 900, state="Italy", fraud="Yes")]
    lines += [row(1, d, "10:00", 20, month=1) for d in range(1, 8)]
    lines += [row(1, d, "12:00", 300, state="United Kingdom", fraud="Yes") for d in (1, 2)]
    lines += [row(1, 9, "11:00", 900, state="United Kingdom", fraud="Yes")]
    csv = tmp_path / "t.csv"
    csv.write_text(HEADER + "".join(lines))
    items, _ = tabformer.build_sample(csv, n_fraud=5, n_legit=0, seed=1)
    by_user = {i["request"]["customer"]["id"]: ScoringRequest.model_validate(i["request"]) for i in items}
    italy, uk = by_user["tf-user-0"], by_user["tf-user-1"]
    assert italy.customer.usual_countries == ["IT"] and uk.customer.usual_countries == ["US"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f_it, f_uk = compute_features(italy, {}, set()), compute_features(uk, {}, set())
    assert not f_it["unusual_country"] and f_it["foreign_merchant"]
    if uk.candidate.timestamp.day == 9:  # the burst's last payment: the UK is in the history, not in the profile
        assert not f_uk["new_country"]
    assert f_uk["unusual_country"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FRAUDCLEF_UI_BACKEND", "fake")
    monkeypatch.setattr(web, "AUDIT_LOG", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(benchmark, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(generator, "GENERATED_DIR", tmp_path / "generated")
    monkeypatch.setattr(tabformer, "RAW_DIR", tmp_path / "raw")
    with TestClient(web.app) as c:
        yield c


def test_console_samples_tabformer(client, tmp_path):
    assert client.get("/api/tabformer").json()["csv"] is False
    assert client.post("/api/tabformer/sample", json={"name": "tf"}).status_code == 409  # not downloaded yet
    (tmp_path / "raw").mkdir()
    lines = [row(u, d, "10:00", 20 + d) for u in range(3) for d in range(1, 6)] + [row(0, 7, "11:00", 900, state="Italy", fraud="Yes")]
    (tmp_path / "raw" / tabformer.CSV_NAME).write_text(HEADER + "".join(lines))
    assert client.get("/api/tabformer").json()["csv"] is True
    assert client.post("/api/tabformer/download", json={}).status_code == 409  # already there
    job = client.post("/api/tabformer/sample", json={"name": "tf", "title": "TF test", "fraud": 1, "legit": 10}).json()["job"]
    for _ in range(200):
        j = client.get(f"/api/tabformer/jobs/{job}").json()
        if j["status"] != "running":
            break
        time.sleep(0.02)
    assert j["status"] == "done" and j["result"]["tabformer"]["fraud"] == 1
    sets = {d["id"]: d for d in client.get("/api/datasets").json()}
    assert sets["generated:tf"]["title"] == "TF test" and sets["generated:tf"]["how"].startswith("Sampled from IBM TabFormer")
    assert client.post("/api/tabformer/sample", json={"name": "tf"}).status_code == 409  # name taken
