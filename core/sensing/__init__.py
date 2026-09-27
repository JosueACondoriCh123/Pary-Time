"""Frente A: sensor y resultado. Dueño: agente externo 1 (ver docs/coordinacion/brief-a.md).

Contrato de `build(ctx)`: devuelve un servicio con `.router`, `.start()`, `.stop()`, `.activity`
(implementa `core.interfaces.ActivitySource`) y `.evaluate_block` (`core.interfaces.EvaluateBlock`) y `.categorize`
(`core.interfaces.Categorize`).
"""
from __future__ import annotations

from core.interfaces import AppContext

from .routes import router


def build(ctx: AppContext):
    from core._stub import StubService
    svc = StubService(router)
    svc.activity = None          # Fase 1: SpanStore sobre SQLite
    svc.evaluate_block = None    # Fase 1: core.sensing.outcome.evaluate_block
    svc.categorize = None        # Fase 1: core.sensing.categorize.categorize
    return svc
