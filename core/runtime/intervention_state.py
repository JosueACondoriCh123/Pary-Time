"""Estado local de las intervenciones (B2): qué se aplicó, qué ventanas se minimizaron, emergencias.

Vive en `data_dir/interventions.sqlite`, separado del store de bloques (B1), y sirve para recuperarse de una caída:
al arrancar, todo lo aplicado y no revertido se restaura. Los `hwnd` y nombres de proceso quedan acá, nunca en el
journal (ahí solo va `n_windows`).
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS application (
  block_id TEXT PRIMARY KEY,
  arm TEXT NOT NULL,
  phase TEXT NOT NULL CHECK (phase IN ('applied', 'reverted', 'recovered')),
  applied_ms INTEGER NOT NULL,
  reverted_ms INTEGER
);
CREATE TABLE IF NOT EXISTS minimized (
  block_id TEXT NOT NULL,
  hwnd INTEGER NOT NULL,
  pid INTEGER NOT NULL DEFAULT 0,
  process TEXT NOT NULL,
  restored INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (block_id, hwnd)
);
CREATE TABLE IF NOT EXISTS flags (
  block_id TEXT PRIMARY KEY,
  emergency INTEGER NOT NULL DEFAULT 0,
  overlay_done INTEGER NOT NULL DEFAULT 0
);
"""


class InterventionState:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(SCHEMA)

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _run(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            db = self._db()
            try:
                with db:
                    return db.execute(sql, args).fetchall()
            finally:
                db.close()

    # ---------------------------------------------------------------- aplicación por bloque

    def phase(self, block_id: str) -> str | None:
        rows = self._run("SELECT phase FROM application WHERE block_id = ?", (block_id,))
        return rows[0][0] if rows else None

    def mark_applied(self, block_id: str, arm: str, now_ms: int) -> None:
        self._run("""INSERT INTO application (block_id, arm, phase, applied_ms) VALUES (?, ?, 'applied', ?)
                     ON CONFLICT(block_id) DO UPDATE SET phase = 'applied', reverted_ms = NULL""",
                  (block_id, arm, now_ms))

    def mark_reverted(self, block_id: str, now_ms: int, phase: str = "reverted") -> None:
        self._run("UPDATE application SET phase = ?, reverted_ms = ? WHERE block_id = ?", (phase, now_ms, block_id))

    def unreverted(self) -> list[tuple[str, str]]:
        """(block_id, arm) aplicados y sin revertir: lo que hay que restaurar tras una caída."""
        return self._run("SELECT block_id, arm FROM application WHERE phase = 'applied'")

    # ---------------------------------------------------------------- ventanas minimizadas

    def add_minimized(self, block_id: str, hwnd: int, pid: int, process: str) -> None:
        """Se anota ANTES de minimizar: si el núcleo muere entre medio, la recuperación igual la restaura."""
        self._run("""INSERT INTO minimized (block_id, hwnd, pid, process) VALUES (?, ?, ?, ?)
                     ON CONFLICT(block_id, hwnd) DO UPDATE SET pid = excluded.pid, restored = 0""",
                  (block_id, hwnd, pid, process))

    def forget_minimized(self, block_id: str, hwnd: int) -> None:
        self._run("DELETE FROM minimized WHERE block_id = ? AND hwnd = ?", (block_id, hwnd))

    def minimized(self, block_id: str) -> list[tuple[int, int]]:
        """(hwnd, pid) minimizados por nosotros y todavía no restaurados."""
        return [(r[0], r[1]) for r in self._run(
            "SELECT hwnd, pid FROM minimized WHERE block_id = ? AND restored = 0", (block_id,))]

    def mark_restored(self, block_id: str) -> None:
        self._run("UPDATE minimized SET restored = 1 WHERE block_id = ?", (block_id,))

    # ---------------------------------------------------------------- banderas

    def _flag(self, block_id: str, name: str) -> bool:
        rows = self._run(f"SELECT {name} FROM flags WHERE block_id = ?", (block_id,))
        return bool(rows and rows[0][0])

    def _set_flag(self, block_id: str, name: str) -> None:
        self._run(f"""INSERT INTO flags (block_id, {name}) VALUES (?, 1)
                      ON CONFLICT(block_id) DO UPDATE SET {name} = 1""", (block_id,))

    def emergency(self, block_id: str) -> bool:
        return self._flag(block_id, "emergency")

    def set_emergency(self, block_id: str) -> None:
        self._set_flag(block_id, "emergency")

    def overlay_done(self, block_id: str) -> bool:
        return self._flag(block_id, "overlay_done")

    def set_overlay_done(self, block_id: str) -> None:
        self._set_flag(block_id, "overlay_done")
