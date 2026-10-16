"""Local SQLite store. Reviews, labels and drafts stay on this machine."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from app.config import get_settings

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_conn_path: str | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY, brand TEXT NOT NULL, source TEXT, author TEXT, rating INTEGER,
  title TEXT, text TEXT NOT NULL, date TEXT, labels TEXT, analyzed_at REAL, created_at REAL
);
CREATE INDEX IF NOT EXISTS reviews_brand ON reviews (brand);
CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT NOT NULL, text TEXT NOT NULL,
  checks TEXT, status TEXT, attempts INTEGER, approved_at REAL, created_at REAL
);
CREATE INDEX IF NOT EXISTS drafts_review ON drafts (review_id);
"""


def _connection() -> sqlite3.Connection:
    global _conn, _conn_path
    path = str(get_settings().db_path)
    if _conn is None or _conn_path != path:
        if path != ":memory:":
            get_settings().db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _conn_path = path
    return _conn


@contextmanager
def db():
    with _lock:
        conn = _connection()
        yield conn
        conn.commit()


def review_id(brand: str, author: str, date: str, text: str) -> str:
    return hashlib.sha1(f"{brand}|{author}|{date}|{text}".encode()).hexdigest()[:12]


def add_reviews(brand: str, source: str, rows: list[dict]) -> int:
    """Inserts new reviews and returns how many were new (duplicates are skipped)."""
    added = 0
    with db() as conn:
        for row in rows:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            rid = review_id(brand, str(row.get("author") or ""), str(row.get("date") or ""), text)
            rating = row.get("rating")
            try:
                rating = int(float(rating)) if rating not in (None, "") else None
            except (TypeError, ValueError):
                rating = None
            cur = conn.execute(
                "INSERT OR IGNORE INTO reviews (id, brand, source, author, rating, title, text, date, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (rid, brand, source, row.get("author") or "", rating, row.get("title") or "", text, row.get("date") or "", time.time()),
            )
            added += cur.rowcount
    return added


def _review(row: sqlite3.Row) -> dict:
    out = dict(row)
    out["labels"] = json.loads(out["labels"]) if out.get("labels") else None
    return out


def list_reviews(brand: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM reviews WHERE brand=? ORDER BY date DESC, created_at DESC", (brand,)).fetchall()
    return [_review(r) for r in rows]


def get_review(rid: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE id=?", (rid,)).fetchone()
    return _review(row) if row else None


def set_labels(rid: str, labels: dict) -> None:
    with db() as conn:
        conn.execute("UPDATE reviews SET labels=?, analyzed_at=? WHERE id=?", (json.dumps(labels), time.time(), rid))


def clear_brand(brand: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM drafts WHERE review_id IN (SELECT id FROM reviews WHERE brand=?)", (brand,))
        conn.execute("DELETE FROM reviews WHERE brand=?", (brand,))


def save_draft(review_id_: str, text: str, checks: list[dict], status: str, attempts: int) -> dict:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO drafts (review_id, text, checks, status, attempts, created_at) VALUES (?,?,?,?,?,?)",
            (review_id_, text, json.dumps(checks), status, attempts, time.time()),
        )
        draft_id = cur.lastrowid
    return get_draft(draft_id)


def update_draft(draft_id: int, text: str, checks: list[dict], status: str) -> dict | None:
    with db() as conn:
        conn.execute("UPDATE drafts SET text=?, checks=?, status=? WHERE id=?", (text, json.dumps(checks), status, draft_id))
    return get_draft(draft_id)


def approve_draft(draft_id: int) -> dict | None:
    with db() as conn:
        conn.execute("UPDATE drafts SET status='approved', approved_at=? WHERE id=?", (time.time(), draft_id))
    return get_draft(draft_id)


def _draft(row: sqlite3.Row) -> dict:
    out = dict(row)
    out["checks"] = json.loads(out["checks"]) if out.get("checks") else []
    return out


def get_draft(draft_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
    return _draft(row) if row else None


def latest_drafts(brand: str) -> dict[str, dict]:
    """Most recent draft for each review of a brand, keyed by review id."""
    with db() as conn:
        rows = conn.execute(
            "SELECT d.* FROM drafts d JOIN reviews r ON r.id = d.review_id WHERE r.brand=? ORDER BY d.id", (brand,)
        ).fetchall()
    return {r["review_id"]: _draft(r) for r in rows}
