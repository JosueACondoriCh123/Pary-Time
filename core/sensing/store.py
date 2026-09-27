"""Thread-safe SQLite activity source. Raw titles never leave this local store."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from core.contracts import ActivitySpan


class SpanStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._db: sqlite3.Connection | None = None
        self._cutoff: int | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA secure_delete=ON")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS spans (
                    start_ms INTEGER PRIMARY KEY, end_ms INTEGER NOT NULL,
                    process TEXT NOT NULL, title TEXT NOT NULL,
                    idle INTEGER NOT NULL, locked INTEGER NOT NULL,
                    CHECK(end_ms > start_ms)
                );
                CREATE INDEX IF NOT EXISTS spans_start ON spans(start_ms);
                CREATE INDEX IF NOT EXISTS spans_end ON spans(end_ms);
                CREATE TABLE IF NOT EXISTS sensor_meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
            """)
            self._db = db
        return self._db

    def write(self, span: ActivitySpan) -> None:
        """Insert a closed span or extend the current span by its original start."""
        with self._lock:
            start = max(span.start_ms, self._cutoff) if self._cutoff is not None else span.start_ms
            if span.end_ms <= start:
                return
            db = self._connect()
            with db:
                overlap = db.execute(
                    "SELECT 1 FROM spans WHERE start_ms != ? AND start_ms < ? AND end_ms > ? LIMIT 1",
                    (start, span.end_ms, start),
                ).fetchone()
                if overlap:
                    raise ValueError("activity spans must not overlap")
                db.execute("""INSERT INTO spans VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(start_ms) DO UPDATE SET end_ms=excluded.end_ms,
                        process=excluded.process, title=excluded.title,
                        idle=excluded.idle, locked=excluded.locked""",
                           (start, span.end_ms, span.process, span.title, span.idle, span.locked))

    def mark_sample(self, sampled_ms: int) -> None:
        with self._lock:
            db = self._connect()
            with db:
                db.execute("INSERT OR REPLACE INTO sensor_meta VALUES ('last_sample_ms', ?)",
                           (sampled_ms,))

    def last_sample_ms(self) -> int | None:
        return self.metadata("last_sample_ms")

    def metadata(self, key: str) -> int | None:
        with self._lock:
            row = self._connect().execute(
                "SELECT value FROM sensor_meta WHERE key=?", (key,)).fetchone()
            return row[0] if row else None

    def set_metadata(self, key: str, value: int | None) -> None:
        with self._lock:
            db = self._connect()
            with db:
                if value is None:
                    db.execute("DELETE FROM sensor_meta WHERE key=?", (key,))
                else:
                    db.execute("INSERT OR REPLACE INTO sensor_meta VALUES (?, ?)", (key, value))

    def spans(self, start_ms: int, end_ms: int) -> list[ActivitySpan]:
        if end_ms <= start_ms:
            return []
        with self._lock:
            rows = self._connect().execute(
                "SELECT start_ms,end_ms,process,title,idle,locked FROM spans "
                "WHERE start_ms < ? AND end_ms > ? ORDER BY start_ms", (end_ms, start_ms),
            ).fetchall()
        return [ActivitySpan(start_ms=max(start_ms, a), end_ms=min(end_ms, b),
                             process=p, title=t, idle=bool(i), locked=bool(k))
                for a, b, p, t, i, k in rows]

    def prune(self, cutoff_ms: int) -> int:
        """Delete expired rows and trim straddling rows; erase freed pages and old WAL frames."""
        with self._lock:
            db = self._connect()
            with db:
                deleted = db.execute("DELETE FROM spans WHERE end_ms <= ?", (cutoff_ms,)).rowcount
                db.execute("UPDATE spans SET start_ms=? WHERE start_ms < ? AND end_ms > ?",
                           (cutoff_ms, cutoff_ms, cutoff_ms))
            self._cutoff = max(cutoff_ms, self._cutoff or cutoff_ms)
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            return deleted

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None
