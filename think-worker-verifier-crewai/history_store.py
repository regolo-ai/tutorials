"""history_store.py — Storage persistente delle sessioni con SQLite."""
from __future__ import annotations
import sqlite3
import json
from typing import List, Optional
from models import SessionState

class HistoryStore:
    def __init__(self, db_path: str = "history.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_input TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    state_json TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_session(self, state: SessionState) -> int:
        state_json = state.model_dump_json()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Cerca se esiste già una sessione con lo stesso input per aggiornarla, altrimenti inserisce
            cursor.execute("SELECT id FROM sessions WHERE user_input = ?", (state.user_input,))
            row = cursor.fetchone()
            if row:
                conn.execute(
                    "UPDATE sessions SET state_json = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?",
                    (state_json, row[0])
                )
                session_id = row[0]
            else:
                cursor.execute(
                    "INSERT INTO sessions (user_input, state_json) VALUES (?, ?)",
                    (state.user_input, state_json)
                )
                session_id = cursor.lastrowid
            conn.commit()
            return session_id

    def list_sessions(self) -> List[dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT id, user_input, timestamp FROM sessions ORDER BY timestamp DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_session(self, session_id: int) -> Optional[SessionState]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT state_json FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                return SessionState.model_validate(data)
        return None
