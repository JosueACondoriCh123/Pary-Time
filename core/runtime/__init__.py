"""Frente B: runtime e intervenciones. Dueño: agente externo 2 (ver docs/coordinacion/brief-b.md).

Contrato de `build(ctx)`: devuelve un servicio con `.router`, `.start()` y `.stop()`. Usa
`ctx.activity`, `ctx.evaluate_block` y `ctx.experiments`; escribe al journal con
`core.journal.append_typed`.
"""
from __future__ import annotations

from core.interfaces import AppContext

from .routes import router


def build(ctx: AppContext):
    from core._stub import StubService
    return StubService(router)
