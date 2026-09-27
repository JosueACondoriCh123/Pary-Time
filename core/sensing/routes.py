"""Rutas del Frente A. Las firmas (path, método, modelos) son contrato: no cambiarlas sin pedido."""
from __future__ import annotations

from fastapi import APIRouter, Query

from core.contracts import ActivitySummary, BlockOutcome


def build_router(service):
    # Instance-bound closures: creating a second app never redirects the first app's data.
    router = APIRouter(tags=["A: sensor y resultado"])

    @router.get("/activity/today", response_model=ActivitySummary)
    def activity_today():
        return service.summary()

    @router.post("/activity/pause", response_model=ActivitySummary)
    def activity_pause(minutes: int = Query(ge=1, le=480)):
        """Pausa de privacidad: el sensor no registra nada durante `minutes`."""
        # Frozen OpenAPI description retained; outcome@1 requires __paused__ coverage.
        service.sampler.pause(minutes)
        return service.summary()

    @router.post("/activity/resume", response_model=ActivitySummary)
    def activity_resume():
        service.sampler.resume()
        return service.summary()

    @router.get("/outcomes", response_model=list[BlockOutcome])
    def outcomes(from_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
                 to_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$")):
        """Outcomes finales del journal en el rango de fechas locales (inclusive)."""
        return service.outcomes(from_date, to_date)

    return router


# Retain the module export used by the original skeleton; build(ctx) binds a fresh router.
router = build_router(None)
