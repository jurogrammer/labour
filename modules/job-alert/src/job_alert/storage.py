from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path

from job_alert.models import JobPost


class StateStore(AbstractContextManager["StateStore"]):
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_posts (
                    source TEXT NOT NULL,
                    source_post_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    first_sent_at TEXT NOT NULL,
                    PRIMARY KEY (source, source_post_id)
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_logs (
                    run_at TEXT PRIMARY KEY,
                    new_count INTEGER NOT NULL,
                    error_count INTEGER NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def mark_sent_if_new(self, post: JobPost, sent_at_utc: str | None = None) -> bool:
        sent_at = sent_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT OR IGNORE INTO sent_posts (source, source_post_id, url, first_sent_at)
                VALUES (?, ?, ?, ?)
                """,
                (post.source, post.source_post_id, post.url, sent_at),
            )
        return cursor.rowcount == 1

    def is_sent(self, post: JobPost) -> bool:
        row = self.conn.execute(
            """
            SELECT 1 FROM sent_posts
            WHERE source = ? AND source_post_id = ?
            LIMIT 1
            """,
            (post.source, post.source_post_id),
        ).fetchone()
        return row is not None

    def get_unsent_posts(self, posts: list[JobPost]) -> list[JobPost]:
        unsent: list[JobPost] = []
        seen_in_batch: set[tuple[str, str]] = set()
        for post in posts:
            key = (post.source, post.source_post_id)
            if key in seen_in_batch:
                continue
            seen_in_batch.add(key)
            if not self.is_sent(post):
                unsent.append(post)
        return unsent

    def mark_posts_sent(self, posts: list[JobPost], sent_at_utc: str | None = None) -> None:
        sent_at = sent_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self.conn:
            self.conn.executemany(
                """
                INSERT OR IGNORE INTO sent_posts (source, source_post_id, url, first_sent_at)
                VALUES (?, ?, ?, ?)
                """,
                [(post.source, post.source_post_id, post.url, sent_at) for post in posts],
            )

    def filter_new_posts(self, posts: list[JobPost], sent_at_utc: str | None = None) -> list[JobPost]:
        new_posts: list[JobPost] = []
        for post in posts:
            if self.mark_sent_if_new(post, sent_at_utc=sent_at_utc):
                new_posts.append(post)
        return new_posts

    def log_run(self, run_at_utc: str, new_count: int, error_count: int) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO run_logs (run_at, new_count, error_count)
                VALUES (?, ?, ?)
                """,
                (run_at_utc, new_count, error_count),
            )

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def set_meta(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO meta (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def count_sent_posts(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS c FROM sent_posts").fetchone()
        return int(row["c"]) if row else 0

    def close(self) -> None:
        self.conn.close()

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()
