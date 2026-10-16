import io

from fastapi.testclient import TestClient

from app import main
from tests.test_core import FakeClient

main.client = FakeClient(choices={"compensation": "no", "blame": "no", "personal_data": "no", "tone": "no", "competitor": "no",
                                  "language": "yes", "unsupported_claim": "no", "acknowledges": "yes"})
api = TestClient(main.app)


def test_flow_sample_analyze_reply_approve():
    assert api.get("/api/health").json()["app"] == "review-reply-copilot"
    assert {b["id"] for b in api.get("/api/brands").json()} >= {"acme-outdoor", "northwind-cloud"}
    assert api.post("/api/reviews/sample", json={"brand": "acme-outdoor"}).json()["added"] > 30
    assert api.post("/api/analyze", json={"brand": "acme-outdoor"}).json()["analyzed"] > 30
    reviews = api.get("/api/reviews", params={"brand": "acme-outdoor"}).json()
    assert all(r["labels"] for r in reviews)
    rid = reviews[0]["id"]
    draft = api.post(f"/api/reviews/{rid}/reply", json={}).json()
    assert draft["status"] == "ready" and draft["checks"]
    approved = api.post(f"/api/drafts/{draft['id']}/approve").json()
    assert approved["status"] == "approved"
    metrics = api.get("/api/metrics", params={"brand": "acme-outdoor"}).json()
    assert metrics["approved"] == 1


def test_approve_refused_when_a_blocking_check_failed():
    main.client = FakeClient(choices={"compensation": "yes"})
    rid = api.get("/api/reviews", params={"brand": "acme-outdoor"}).json()[1]["id"]
    draft = api.post(f"/api/reviews/{rid}/reply", json={}).json()
    assert draft["status"] == "needs_edit"
    assert api.post(f"/api/drafts/{draft['id']}/approve").status_code == 409


def test_csv_import_with_flexible_columns_and_errors():
    csv_bytes = b"Name,Stars,Review,Created\nAnna,4,Nice boots,2026-01-02\n"
    out = api.post("/api/reviews/csv", data={"brand": "northwind-cloud"}, files={"file": ("r.csv", io.BytesIO(csv_bytes), "text/csv")}).json()
    assert out["added"] == 1
    assert api.post("/api/reviews/csv", data={"brand": "northwind-cloud"}, files={"file": ("e.csv", io.BytesIO(b"text\n"), "text/csv")}).status_code == 400
    assert api.get("/api/reviews", params={"brand": "nope"}).status_code == 404


def test_template_download_and_import_round_trip():
    template = api.get("/api/template.csv")
    assert template.status_code == 200 and template.text.splitlines()[0] == "author,rating,title,text,date"
    assert api.post("/api/reviews/csv", data={"brand": "acme-outdoor"}, files={"file": ("t.csv", io.BytesIO(template.content), "text/csv")}).json()["added"] == 3


def test_progress_endpoint_reports_state():
    body = api.get("/api/analyze/progress").json()
    assert set(body) >= {"running", "done", "total", "elapsed"}
