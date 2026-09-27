"""SQLite local de bloques. Títulos, etiquetas y rutas viven acá y no salen al journal."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from core.contracts import Arm, Block, BlockStatus


class BlockNotFound(Exception):
    pass


class BlockConflict(Exception):
    def __init__(self, detail: str):
        self.detail = detail


class BlockInvalid(Exception):
    pass


@dataclass
class StoredBlock:
    block: Block
    arm: Arm | None
    experiment_id: str | None
    draw_index: int | None
    assigned_ms: int | None


class BlockStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._db: sqlite3.Connection | None = None

    @contextmanager
    def locked(self):
        with self._lock:
            yield

    def _connect(self) -> sqlite3.Connection:
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS blocks (
                    block_id TEXT PRIMARY KEY,
                    local_date TEXT NOT NULL,
                    planned_start_ms INTEGER NOT NULL,
                    planned_minutes INTEGER NOT NULL,
                    task_kind TEXT NOT NULL,
                    task_label TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_value TEXT NOT NULL,
                    work_matchers TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_ms INTEGER NOT NULL,
                    first_step TEXT,
                    aborted INTEGER NOT NULL DEFAULT 0,
                    arm TEXT,
                    experiment_id TEXT,
                    draw_index INTEGER,
                    assigned_ms INTEGER
                );
                CREATE INDEX IF NOT EXISTS blocks_day
                    ON blocks(local_date, planned_start_ms, block_id);
            """)
            self._db = db
        return self._db

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._db.close()
                self._db = None

    def insert(self, block: Block) -> StoredBlock:
        with self._lock:
            db = self._connect()
            with db:
                db.execute(
                    """INSERT INTO blocks (
                        block_id, local_date, planned_start_ms, planned_minutes, task_kind,
                        task_label, target_kind, target_value, work_matchers, status, created_ms,
                        first_step, aborted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    _block_values(block),
                )
        return StoredBlock(block, None, None, None, None)

    def get(self, block_id: str) -> StoredBlock | None:
        with self._lock:
            row = self._connect().execute(
                "SELECT * FROM blocks WHERE block_id=?", (block_id,)).fetchone()
        return _record(row) if row else None

    def list_day(self, local_date: str) -> list[StoredBlock]:
        with self._lock:
            rows = self._connect().execute(
                """SELECT * FROM blocks WHERE local_date=?
                   ORDER BY planned_start_ms, block_id""",
                (local_date,),
            ).fetchall()
        return [_record(row) for row in rows]

    def replace_planned(self, block: Block) -> None:
        """Reemplaza los campos editables. Falla si el bloque no está `planned`."""
        with self._lock:
            db = self._connect()
            with db:
                found = db.execute(
                    "SELECT status FROM blocks WHERE block_id=?", (block.block_id,)).fetchone()
                if found is None:
                    raise BlockNotFound()
                if found["status"] != BlockStatus.planned.value:
                    raise BlockConflict("solo se edita un bloque planned")
                db.execute(
                    """UPDATE blocks SET local_date=?, planned_start_ms=?, planned_minutes=?,
                       task_kind=?, task_label=?, target_kind=?, target_value=?, work_matchers=?,
                       status=?, created_ms=?, first_step=?, aborted=? WHERE block_id=?""",
                    _block_values(block)[1:] + (block.block_id,),
                )

    def cancel(self, block_id: str) -> StoredBlock:
        with self._lock:
            db = self._connect()
            with db:
                found = db.execute(
                    "SELECT status FROM blocks WHERE block_id=?", (block_id,)).fetchone()
                if found is None:
                    raise BlockNotFound()
                if found["status"] != BlockStatus.planned.value:
                    raise BlockConflict("solo se cancela un bloque planned")
                db.execute(
                    "UPDATE blocks SET status=? WHERE block_id=?",
                    (BlockStatus.cancelled.value, block_id),
                )
            row = db.execute("SELECT * FROM blocks WHERE block_id=?", (block_id,)).fetchone()
        return _record(row)

    def mark_confirmed(self, block_id: str) -> None:
        with self._lock:
            db = self._connect()
            with db:
                cur = db.execute(
                    "UPDATE blocks SET status=? WHERE block_id=? AND status=?",
                    (BlockStatus.confirmed.value, block_id, BlockStatus.planned.value),
                )
                if cur.rowcount == 1:
                    return
                found = db.execute(
                    "SELECT 1 FROM blocks WHERE block_id=?", (block_id,)).fetchone()
            if found is None:
                raise BlockNotFound()
            raise BlockConflict("solo se confirma un bloque planned")

    def save_assignment(self, block_id: str, arm: Arm, experiment_id: str | None,
                        draw_index: int | None, assigned_ms: int) -> None:
        with self._lock:
            db = self._connect()
            with db:
                cur = db.execute(
                    """UPDATE blocks SET arm=?, experiment_id=?, draw_index=?, assigned_ms=?
                       WHERE block_id=?""",
                    (arm.value, experiment_id, draw_index, assigned_ms, block_id),
                )
                if cur.rowcount != 1:
                    raise BlockNotFound()

    def set_first_step(self, block_id: str, text: str) -> StoredBlock:
        with self._lock:
            db = self._connect()
            with db:
                cur = db.execute(
                    "UPDATE blocks SET first_step=? WHERE block_id=?", (text, block_id))
                if cur.rowcount != 1:
                    raise BlockNotFound()
            row = db.execute("SELECT * FROM blocks WHERE block_id=?", (block_id,)).fetchone()
        return _record(row)

    # ---------------------------------------------------------------- B2 (scheduler)

    def pending(self) -> list[StoredBlock]:
        """Bloques `confirmed` o `running` de cualquier fecha, en orden de inicio."""
        with self._lock:
            rows = self._connect().execute(
                "SELECT * FROM blocks WHERE status IN (?, ?) ORDER BY planned_start_ms, block_id",
                (BlockStatus.confirmed.value, BlockStatus.running.value)).fetchall()
        return [_record(row) for row in rows]

    def set_status(self, block_id: str, status: BlockStatus) -> None:
        with self._lock:
            db = self._connect()
            with db:
                if db.execute("UPDATE blocks SET status=? WHERE block_id=?",
                              (status.value, block_id)).rowcount != 1:
                    raise BlockNotFound()

    def set_aborted(self, block_id: str) -> None:
        with self._lock:
            db = self._connect()
            with db:
                if db.execute("UPDATE blocks SET aborted=1 WHERE block_id=?", (block_id,)).rowcount != 1:
                    raise BlockNotFound()


def _block_values(block: Block) -> tuple:
    matchers = json.dumps([item.model_dump(mode="json") for item in block.work_matchers],
                          ensure_ascii=False)
    return (
        block.block_id, block.local_date, block.planned_start_ms, block.planned_minutes,
        block.task_kind.value, block.task_label, block.target.kind, block.target.value, matchers,
        block.status.value, block.created_ms, block.first_step, int(block.aborted),
    )


def _record(row: sqlite3.Row) -> StoredBlock:
    block = Block.model_validate({
        "block_id": row["block_id"],
        "local_date": row["local_date"],
        "planned_start_ms": row["planned_start_ms"],
        "planned_minutes": row["planned_minutes"],
        "task_kind": row["task_kind"],
        "task_label": row["task_label"],
        "target": {"kind": row["target_kind"], "value": row["target_value"]},
        "work_matchers": json.loads(row["work_matchers"]),
        "status": row["status"],
        "created_ms": row["created_ms"],
        "first_step": row["first_step"],
        "aborted": bool(row["aborted"]),
    })
    arm = Arm(row["arm"]) if row["arm"] is not None else None
    return StoredBlock(block, arm, row["experiment_id"], row["draw_index"], row["assigned_ms"])
