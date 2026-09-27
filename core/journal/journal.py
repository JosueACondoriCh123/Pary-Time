# Copiado de Night Council (night_council/journal.py, mismo autor). Cambios: import de canon,
# campos prohibidos ampliados a títulos de ventana y textos del usuario.
"""Diario append-only con cadena de hashes.

Cada línea es un evento JSON con `prev` (hash de la línea anterior) y `hash`
(sha256 del evento canónico sin el campo hash). Alterar, borrar o reordenar
cualquier línea rompe `verify()`. Es la fuente de verdad para la auditoría y
para reconstruir el estado tras una caída.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Iterator

from .canon import canonical, sha256

GENESIS = "0" * 64

# Nombres de campo que jamás deben aparecer en el diario.
_FORBIDDEN = ("secret", "private_key", "api_key", "apikey", "password", "mnemonic", "token",
              # Privacidad N-de-1: el journal se comparte, así que nunca lleva títulos de ventana
              # ni textos escritos por el usuario (viven solo en el SQLite local).
              "title", "task_label", "first_step", "work_matchers", "target")


class JournalError(Exception):
    pass


def new_decision_id() -> str:
    return "dec_" + uuid.uuid4().hex


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.torn_tail: str | None = None      # última línea a medio escribir (corte de luz)
        self.repaired: Path | None = None      # dónde quedó guardada, si hubo que recortarla
        self._cache: list[dict] = []           # eventos ya parseados, en orden
        self._parsed = 0                       # bytes del archivo ya parseados
        self._parses = 0                       # solo para medir: cuántas líneas se parsearon
        self._last_hash, self._seq = self._tail()

    def _tail(self) -> tuple[str, int]:
        last, seq = GENESIS, 0
        for ev in self.events():
            last, seq = ev["hash"], ev["seq"]
        return last, seq

    def _refresh(self) -> None:
        """Parsea solo los bytes nuevos.

        El diario es append-only, así que lo ya parseado no puede cambiar. Antes cada consulta
        releía y reparseaba el archivo entero, y un ciclo hace ocho o nueve consultas: con
        catorce días de diario eso crecía sin techo. Si el archivo encogió (lo recortamos tras
        una línea rota, o es otro diario) se relee desde cero.
        """
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            self._cache, self._parsed, self.torn_tail = [], 0, None
            return
        if size < self._parsed:
            self._cache, self._parsed = [], 0
        if size == self._parsed:
            return
        with self.path.open("rb") as f:
            f.seek(self._parsed)
            chunk = f.read()
        parts = chunk.decode("utf-8").split("\n")
        # Lo que viene después del último salto de línea todavía no es un evento: `append`
        # siempre termina en salto, así que una cola sin salto es una escritura a medio hacer.
        tail = parts.pop()
        for line in parts:
            if not line.strip():
                continue
            try:
                self._cache.append(json.loads(line))
                self._parses += 1
            except json.JSONDecodeError as e:
                raise JournalError(f"línea {len(self._cache) + 1} ilegible: {e}") from e
        self._parsed += len(chunk) - len(tail.encode("utf-8"))
        self.torn_tail = tail if tail.strip() else None

    def events(self) -> Iterator[dict]:
        """Eventos del diario, de solo lectura (no los mutes: son los del caché).

        Tolera que la última línea esté a medio escribir —un corte de luz entre el write y el
        fsync— y la deja en `torn_tail`: esa línea nunca fue un evento, no tiene hash y nadie
        la encadenó. Una línea completa ilegible sí es corrupción y lanza JournalError."""
        self._refresh()
        return iter(tuple(self._cache))

    def _heal_torn_tail(self) -> Path:
        """Guarda la línea rota al lado y recorta el archivo, para poder seguir encadenando.
        No es reescribir la historia: se descarta algo que nunca llegó a ser un evento."""
        raw = self.path.read_bytes()
        tail = self.torn_tail.encode("utf-8")
        idx = len(raw) - len(tail) if raw.endswith(tail) else raw.rfind(tail)
        saved = self.path.parent / f"{self.path.name}.torn-{int(time.time())}"
        saved.write_bytes(raw[idx:])
        with self.path.open("rb+") as f:
            f.truncate(idx)
            f.flush()
            os.fsync(f.fileno())
        self.torn_tail, self.repaired = None, saved
        return saved

    def append(self, kind: str, payload: dict, agent_version: str) -> dict:
        _check_no_secrets(payload)
        with self._lock:
            if self.torn_tail is not None:
                self._heal_torn_tail()
            ev = {
                "seq": self._seq + 1,
                "ts": time.time(),
                "kind": kind,
                "agent_version": agent_version,
                "payload": payload,
                "prev": self._last_hash,
            }
            ev["hash"] = sha256(canonical(ev))
            line = canonical(ev) + "\n"
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            self._last_hash, self._seq = ev["hash"], ev["seq"]
            return ev

    def verify(self) -> int:
        """Devuelve el número de eventos válidos o lanza JournalError."""
        prev, n = GENESIS, 0
        for ev in self.events():
            body = {k: v for k, v in ev.items() if k != "hash"}
            if ev["prev"] != prev:
                raise JournalError(f"seq {ev['seq']}: prev no coincide")
            if sha256(canonical(body)) != ev["hash"]:
                raise JournalError(f"seq {ev['seq']}: hash alterado")
            if ev["seq"] != n + 1:
                raise JournalError(f"seq {ev['seq']}: hueco en la secuencia")
            prev, n = ev["hash"], ev["seq"]
        return n


def _check_no_secrets(obj, path="payload") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(f in str(k).lower() for f in _FORBIDDEN):
                raise JournalError(f"campo prohibido en el diario: {path}.{k}")
            _check_no_secrets(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_no_secrets(v, f"{path}[{i}]")
