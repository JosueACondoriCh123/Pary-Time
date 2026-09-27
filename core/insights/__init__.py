"""Historial de uso agregado para la pantalla "Mi tiempo" (Frente 0/C).

Lee los tramos del sensor (`ctx.activity`, Frente A) y los bloques del día (`ctx.blocks_on`, armado en core/app.py)
y devuelve solo agregados: por día, por hora, por app y por sitio de distracción. Nunca títulos de ventana.
"""
from __future__ import annotations

import time
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from core.contracts import ActivityHistory
from core.insights.aggregate import _day_start_ms, compute_history
from core.interfaces import AppContext

MAX_RANGE_DAYS = 31


class InsightsService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.router = APIRouter(tags=["0/C: historial de uso"])

        @self.router.get("/activity/history", response_model=ActivityHistory)
        def history(from_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
                    to_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$")):
            """Agregados del rango de fechas locales (inclusive). Máximo 31 días; los tramos crudos se conservan
            `raw_retention_days` (14 por defecto), así que lo anterior sale vacío."""
            a, b = date.fromisoformat(from_date), date.fromisoformat(to_date)
            if b < a or (b - a).days + 1 > MAX_RANGE_DAYS:
                raise HTTPException(status_code=422, detail=f"rango inválido (máximo {MAX_RANGE_DAYS} días)")
            return self.history(a, b)

    def history(self, a: date, b: date, now_ms: int | None = None) -> ActivityHistory:
        now_ms = time.time_ns() // 1_000_000 if now_ms is None else now_ms
        if self.ctx.activity is None or self.ctx.categorize is None:
            raise HTTPException(status_code=503, detail="el sensor no está disponible")
        spans = self.ctx.activity.spans(_day_start_ms(a), _day_start_ms(b + timedelta(days=1)))
        return compute_history(spans, self.ctx.blocks_on, self.ctx.settings(), self.ctx.categorize, a, b, now_ms)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def build(ctx: AppContext) -> InsightsService:
    return InsightsService(ctx)
