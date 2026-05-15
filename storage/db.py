"""Lightweight SQLite layer for users, sessions, and a paper cache.

Kept small on purpose: features only need three things —
    * remember a user
    * remember the last paper text the user uploaded (so /gaps, /interpret can reuse)
    * cache lit-review searches so repeated queries are cheap
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sources.models import Paper

log = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_state (
    user_id        INTEGER PRIMARY KEY,
    last_paper     TEXT,
    last_paper_at  INTEGER,
    citation_style TEXT DEFAULT 'APA'
);

CREATE TABLE IF NOT EXISTS search_cache (
    query       TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    cached_at   INTEGER NOT NULL
);
"""

CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 hours


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)

    # ---- users ----------------------------------------------------------
    def upsert_user(self, user_id: int, username: str | None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO users(user_id, username, created_at) VALUES(?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
                (user_id, username or "", int(time.time())),
            )

    # ---- user state -----------------------------------------------------
    def set_last_paper(self, user_id: int, text: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO user_state(user_id, last_paper, last_paper_at) VALUES(?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET last_paper=excluded.last_paper, "
                "last_paper_at=excluded.last_paper_at",
                (user_id, text, int(time.time())),
            )

    def get_last_paper(self, user_id: int) -> str | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT last_paper FROM user_state WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return row["last_paper"] if row and row["last_paper"] else None

    def set_citation_style(self, user_id: int, style: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO user_state(user_id, citation_style) VALUES(?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET citation_style=excluded.citation_style",
                (user_id, style),
            )

    def get_citation_style(self, user_id: int) -> str:
        with self._conn() as c:
            row = c.execute(
                "SELECT citation_style FROM user_state WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return (row["citation_style"] if row and row["citation_style"] else "APA")

    # ---- search cache ---------------------------------------------------
    def cache_search(self, query: str, papers: list[Paper]) -> None:
        payload = json.dumps([p.__dict__ for p in papers])
        with self._conn() as c:
            c.execute(
                "INSERT INTO search_cache(query, payload, cached_at) VALUES(?, ?, ?) "
                "ON CONFLICT(query) DO UPDATE SET payload=excluded.payload, "
                "cached_at=excluded.cached_at",
                (query.lower().strip(), payload, int(time.time())),
            )

    def get_cached_search(self, query: str) -> list[Paper] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT payload, cached_at FROM search_cache WHERE query=?",
                (query.lower().strip(),),
            ).fetchone()
        if not row:
            return None
        if int(time.time()) - int(row["cached_at"]) > CACHE_TTL_SECONDS:
            return None
        try:
            return [Paper(**d) for d in json.loads(row["payload"])]
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to decode cached search: %s", exc)
            return None
