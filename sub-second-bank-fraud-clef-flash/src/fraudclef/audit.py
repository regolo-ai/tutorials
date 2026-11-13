"""Append-only JSONL audit log with a hash chain: each record stores the hash of the previous
one, so any edit, deletion or reordering is detectable with `verify`."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class AuditLog:
    def __init__(self, path: str | Path, hash_chain: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.hash_chain = hash_chain
        self._lock = asyncio.Lock()

    def _last_hash(self) -> str:
        """Hash of the last record on disk. Read on every append, so several AuditLog objects in
        one process (one per engine) extend the same chain instead of forking it."""
        if not self.path.exists() or not self.path.stat().st_size:
            return GENESIS
        with self.path.open("rb") as f:
            size = f.seek(0, 2)
            chunk = 4096
            while True:
                f.seek(max(0, size - chunk))
                lines = [l for l in f.read().splitlines() if l.strip()]
                if len(lines) > 1 or chunk >= size:
                    break
                chunk *= 4
        return json.loads(lines[-1])["record_hash"] if lines else GENESIS

    async def append(self, record: dict[str, Any]) -> None:
        async with self._lock:
            record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
            # No await between reading the last hash and writing: the append is atomic in the event loop.
            if self.hash_chain:
                prev = self._last_hash()
                record["prev_hash"] = prev
                record["record_hash"] = sha256(prev + canonical(record))
            with self.path.open("a") as f:
                f.write(canonical(record) + "\n")


def read_records(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def verify(path: str | Path) -> tuple[bool, int, str]:
    """Return (ok, records_checked, message)."""
    prev = GENESIS
    n = 0
    with Path(path).open() as f:
        for n, line in enumerate(f, 1):
            rec = json.loads(line)
            claimed = rec.pop("record_hash", None)
            if rec.get("prev_hash") != prev:
                return False, n, f"line {n}: prev_hash does not match the previous record"
            if sha256(prev + canonical(rec)) != claimed:
                return False, n, f"line {n}: record content was modified"
            prev = claimed
    return True, n, "hash chain intact"
