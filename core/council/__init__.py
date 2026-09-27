"""Frente C: consejo y estadística. Dueño: Claude (sesión principal).

Contrato de `build(ctx)`: devuelve un servicio con `.router`, `.start()`, `.stop()` y
`.experiments` (implementa `core.interfaces.ExperimentProvider`).
"""
from __future__ import annotations

from core.interfaces import AppContext

from .routes import router


def build(ctx: AppContext):
    from core._stub import StubService
    svc = StubService(router)
    svc.experiments = None
    return svc
