from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class SqliteJsonCache:
    """Small persistent JSON cache for GitHub API responses.

    Keys are caller-defined stable strings. Expired entries are retained so callers
    can optionally fall back to stale data during API outages or rate-limit pressure.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS api_cache (
                key TEXT PRIMARY KEY,
                fetched_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                value_json TEXT NOT NULL
            )
            """
        )
        self.db.commit()

    @staticmethod
    def request_key(query: str, variables: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"query": " ".join(query.split()), "variables": variables},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def get(self, key: str, *, allow_stale: bool = False) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT expires_at, value_json FROM api_cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        expires_at, value_json = row
        if not allow_stale and float(expires_at) < time.time():
            return None
        return json.loads(value_json)

    def put(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        now = time.time()
        self.db.execute(
            """
            INSERT INTO api_cache(key, fetched_at, expires_at, value_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              fetched_at=excluded.fetched_at,
              expires_at=excluded.expires_at,
              value_json=excluded.value_json
            """,
            (key, now, now + ttl_seconds, json.dumps(value, sort_keys=True)),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()
