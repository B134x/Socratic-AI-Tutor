"""SQLite persistence: sessions, an event log, and per-learner mastery that carries across sessions.

Learners are identified only by a class code and a learner code chosen by the teacher;
answer text is never stored, only the checker's verdict and the mastery change.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    class_code TEXT NOT NULL,
    learner_code TEXT NOT NULL,
    lang TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_class ON sessions (class_code, updated_at);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions (id),
    at TEXT NOT NULL,
    step TEXT NOT NULL,
    action TEXT NOT NULL,
    verdict TEXT,
    concept TEXT,
    p_before REAL,
    p_after REAL,
    scored INTEGER NOT NULL DEFAULT 0,
    flagged INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mastery (
    class_code TEXT NOT NULL,
    learner_code TEXT NOT NULL,
    concept TEXT NOT NULL,
    p REAL NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (class_code, learner_code, concept)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # One connection per call: the HTTP server is threaded and sqlite3 connections are not shared.
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_session(self, class_code: str, learner_code: str, lang: str, state: dict) -> str:
        session_id = uuid.uuid4().hex
        now = _now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO sessions (id, class_code, learner_code, lang, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, class_code, learner_code, lang, json.dumps(state), now, now),
            )
        return session_id

    def get_session(self, session_id: str) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["state"] = json.loads(data["state"])
        return data

    def log_event(self, session_id: str, step: str, action: str) -> None:
        with closing(self._connect()) as conn, conn:
            self._insert_event(conn, session_id, step, action)

    def save_turn(self, session_id: str, state: dict, step: str, action: str, *, verdict: str = "", concept: str = "",
                  p_before: float | None = None, p_after: float | None = None, scored: bool = False,
                  flagged: bool = False, mastery_owner: tuple[str, str] | None = None) -> None:
        """New state, the event and (when scored) the learner's mastery, in one transaction."""
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE sessions SET state = ?, updated_at = ? WHERE id = ?", (json.dumps(state), _now(), session_id))
            self._insert_event(conn, session_id, step, action, verdict, concept, p_before, p_after, scored, flagged)
            if mastery_owner is not None:
                now = _now()
                conn.executemany(
                    "INSERT INTO mastery (class_code, learner_code, concept, p, updated_at) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT (class_code, learner_code, concept) DO UPDATE SET p = excluded.p, updated_at = excluded.updated_at",
                    [(*mastery_owner, c, p, now) for c, p in state["mastery"].items()],
                )

    @staticmethod
    def _insert_event(conn: sqlite3.Connection, session_id: str, step: str, action: str, verdict: str = "",
                      concept: str = "", p_before: float | None = None, p_after: float | None = None,
                      scored: bool = False, flagged: bool = False) -> None:
        conn.execute(
            "INSERT INTO events (session_id, at, step, action, verdict, concept, p_before, p_after, scored, flagged) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, _now(), step, action, verdict or None, concept or None, p_before, p_after, int(scored), int(flagged)),
        )

    def prior_mastery(self, class_code: str, learner_code: str) -> dict[str, float]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT concept, p FROM mastery WHERE class_code = ? AND learner_code = ?",
                                (class_code, learner_code)).fetchall()
        return {r["concept"]: r["p"] for r in rows}

    def class_summary(self, class_code: str) -> list[dict]:
        """Latest session per learner in a class, newest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT s.*, ROW_NUMBER() OVER (
                        PARTITION BY learner_code ORDER BY updated_at DESC, created_at DESC, rowid DESC) AS rn
                    FROM sessions s WHERE class_code = ?
                ) WHERE rn = 1
                ORDER BY updated_at DESC
                """,
                (class_code,),
            ).fetchall()
        out = []
        for row in rows:
            data = dict(row)
            data.pop("rn", None)
            data["state"] = json.loads(data["state"])
            out.append(data)
        return out
