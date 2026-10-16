"""Review Reply Copilot: classify reviews with Clef-Flash, draft replies with a chat model, check them, approve."""
from __future__ import annotations

import csv
import io
import threading
import time
from pathlib import Path

import requests
from fastapi import Body, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import account, brands, classify, reply, store
from app.config import get_settings
from app.regolo import Meter, RegoloClient, RegoloError

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Review Reply Copilot")
meter = Meter()
client = RegoloClient(meter=meter)
last_analysis: dict = {}
progress: dict = {"running": False, "done": 0, "total": 0, "started": 0.0}
_progress_lock = threading.Lock()


def _brand(brand_id: str) -> dict:
    try:
        return brands.get_brand(brand_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RegoloError as error:
        raise HTTPException(400, str(error)) from error
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else 502
        raise HTTPException(502, f"Regolo returned HTTP {status}.") from error
    except requests.RequestException as error:
        raise HTTPException(502, f"Could not reach Regolo: {error.__class__.__name__}") from error


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {"app": "review-reply-copilot", "regolo_key_set": account.hint(s.regolo_api_key) is not None,
            "chat_model": s.chat_model, "decision_model": s.decision_model}


@app.get("/api/account")
def account_status() -> dict:
    return account.status()


@app.post("/api/account/key")
def save_key(payload: dict = Body(...), x_rrc: str | None = Header(default=None)) -> dict:
    if x_rrc != "1":  # a page on another site cannot send this custom header without our permission
        raise HTTPException(403, "Missing request header.")
    key = (payload.get("key") or "").strip()
    try:
        account.verify(key)
    except account.KeyError_ as error:
        raise HTTPException(400, str(error)) from error
    except requests.RequestException as error:
        raise HTTPException(502, f"Could not reach Regolo to verify the key: {error.__class__.__name__}") from error
    account.save(key)
    client.settings = get_settings()
    client._prices = None
    return account.status()


@app.get("/api/brands")
def list_brands() -> list[dict]:
    return brands.list_brands()


@app.get("/api/brands/{brand_id}")
def brand_profile(brand_id: str) -> dict:
    return _brand(brand_id)


def _view(brand_id: str) -> list[dict]:
    drafts = store.latest_drafts(brand_id)
    rows = store.list_reviews(brand_id)
    for row in rows:
        row["draft"] = drafts.get(row["id"])
    return rows


@app.get("/api/reviews")
def reviews(brand: str) -> list[dict]:
    _brand(brand)
    return _view(brand)


@app.post("/api/reviews/sample")
def load_sample(payload: dict = Body(...)) -> dict:
    brand_id = payload["brand"]
    _brand(brand_id)
    path = get_settings().data_dir / f"sample_reviews_{brand_id}.csv"
    if not path.exists():
        raise HTTPException(404, "No sample file for this brand.")
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    return {"added": store.add_reviews(brand_id, "sample", rows), "total": len(store.list_reviews(brand_id))}


@app.post("/api/reviews/reset")
def reset(payload: dict = Body(...)) -> dict:
    _brand(payload["brand"])
    store.clear_brand(payload["brand"])
    return {"ok": True}


def parse_csv(content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    aliases = {"text": ("text", "review", "body", "content", "comment", "review text", "review content"),
               "rating": ("rating", "stars", "score", "review rating"),
               "title": ("title", "headline", "subject", "review title"),
               "author": ("author", "name", "user", "reviewer", "reviewer name", "consumer"),
               "date": ("date", "created", "published", "review date", "date of experience")}
    rows = []
    for raw in reader:
        low = {(k or "").strip().lower(): v for k, v in raw.items()}
        row = {}
        for key, names in aliases.items():
            row[key] = next((low[n] for n in names if n in low and low[n] not in (None, "")), "")
        rows.append(row)
    return rows


@app.post("/api/reviews/csv")
async def import_csv(brand: str = Form(...), file: UploadFile = File(...)) -> dict:
    _brand(brand)
    content = (await file.read()).decode("utf-8-sig", errors="replace")
    rows = parse_csv(content)
    if not rows:
        raise HTTPException(400, "The CSV has no rows. Expected a header with at least a text or review column.")
    return {"added": store.add_reviews(brand, "csv", rows), "total": len(store.list_reviews(brand))}


@app.get("/api/template.csv")
def template() -> FileResponse:
    return FileResponse(get_settings().data_dir / "reviews-template.csv", media_type="text/csv", filename="reviews-template.csv")


@app.get("/api/analyze/progress")
def analyze_progress() -> dict:
    with _progress_lock:
        return {**progress, "elapsed": (time.monotonic() - progress["started"]) if progress["running"] else 0.0}


def _tick(count: int) -> None:
    with _progress_lock:
        progress["done"] += count


@app.post("/api/analyze")
def analyze(payload: dict = Body(...)) -> dict:
    brand = _brand(payload["brand"])
    pending = [r for r in store.list_reviews(brand["id"]) if not r["labels"]]
    if not pending:
        return {"analyzed": 0}
    before = client.meter.snapshot()["decide"]
    started = time.monotonic()
    with _progress_lock:
        progress.update({"running": True, "done": 0, "total": len(pending), "started": started})
    try:
        results = _call(classify.classify_reviews, client, brand, pending, _tick)
    finally:
        with _progress_lock:
            progress["running"] = False
    wall = time.monotonic() - started
    for review, labels in zip(pending, results):
        store.set_labels(review["id"], labels)
    after = client.meter.snapshot()["decide"]
    last_analysis.update({
        "reviews": len(pending), "seconds": wall, "requests": after["calls"] - before["calls"],
        "cost_usd": after["cost_usd"] - before["cost_usd"],
    })
    return {"analyzed": len(pending), **last_analysis}


@app.post("/api/reviews/{review_id}/reply")
def make_reply(review_id: str, payload: dict = Body(default={})) -> dict:
    review = store.get_review(review_id)
    if not review:
        raise HTTPException(404, "Unknown review.")
    brand = _brand(review["brand"])
    result = _call(reply.draft_reply, client, brand, review, review["labels"], payload.get("feedback"))
    return store.save_draft(review_id, result["text"], result["checks"], result["status"], result["attempts"])


@app.post("/api/drafts/{draft_id}/check")
def check_draft(draft_id: int, payload: dict = Body(...)) -> dict:
    draft = store.get_draft(draft_id)
    if not draft:
        raise HTTPException(404, "Unknown draft.")
    review = store.get_review(draft["review_id"])
    result = _call(reply.recheck, client, _brand(review["brand"]), review, review["labels"], payload["text"])
    return store.update_draft(draft_id, payload["text"], result["checks"], result["status"])


@app.post("/api/drafts/{draft_id}/approve")
def approve(draft_id: int) -> dict:
    draft = store.get_draft(draft_id)
    if not draft:
        raise HTTPException(404, "Unknown draft.")
    if draft["status"] == "needs_edit":
        raise HTTPException(409, "Fix the failed checks before approving, or edit the text and check it again.")
    return store.approve_draft(draft_id)


@app.get("/api/metrics")
def metrics(brand: str) -> dict:
    rows = store.list_reviews(brand)
    drafts = store.latest_drafts(brand)
    return {"usage": meter.snapshot(), "last_analysis": dict(last_analysis), "reviews": len(rows), "analyzed": sum(1 for r in rows if r["labels"]),
            "drafts": len(drafts), "approved": sum(1 for d in drafts.values() if d["status"] == "approved")}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
