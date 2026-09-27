"""Journal con cadena de hashes, compartido por todos los frentes dentro del proceso núcleo.

Un solo proceso escribe (lo garantiza `LoopLock` en `core/app.py`) y, dentro del proceso, el
`Journal` serializa con su propio lock. Los frentes escriben SIEMPRE con `append_typed`, que valida
el payload contra `core.contracts.JOURNAL_PAYLOADS`: así ningún evento lleva campos fuera de contrato.
"""
from __future__ import annotations

from pydantic import BaseModel

from core.contracts import JOURNAL_PAYLOADS

from .journal import GENESIS, Journal, JournalError, new_decision_id
from .proclock import LoopLock, LoopLockError, pid_alive

AGENT_VERSION = "n-de-1@0.1.0"


def append_typed(journal: Journal, kind: str, payload: BaseModel | dict | None = None) -> dict:
    if kind not in JOURNAL_PAYLOADS:
        raise JournalError(f"tipo de evento fuera de contrato: {kind}")
    model = JOURNAL_PAYLOADS[kind]
    if model is None:
        body = dict(payload or {})
    else:
        obj = payload if isinstance(payload, model) else model.model_validate(payload)
        body = obj.model_dump(mode="json")
    return journal.append(kind, body, AGENT_VERSION)


__all__ = ["AGENT_VERSION", "GENESIS", "Journal", "JournalError", "LoopLock", "LoopLockError",
           "append_typed", "new_decision_id", "pid_alive"]
