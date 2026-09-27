"""Rutas del Frente C. Las firmas (path, método, modelos) son contrato: `make_router` las ata al servicio."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.contracts import (CouncilRun, ExperimentProgress, ExperimentRecord, LedgerEntry, Report,
                            VetoRegret)
from core.council.journal_view import JournalView


def make_router(svc) -> APIRouter:
    router = APIRouter(tags=["C: consejo y estadística"])

    @router.get("/experiments/current", response_model=ExperimentProgress | None)
    def current_experiment():
        """Progreso del experimento en curso, SIN efecto hasta llegar al N. null si no hay."""
        return svc.experiments.progress()

    @router.get("/experiments", response_model=list[ExperimentRecord])
    def experiments():
        return svc.experiments.records()

    @router.post("/council/run", response_model=CouncilRun)
    def run_council():
        """Reunión manual del consejo (además de la semanal automática)."""
        if not svc.run_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="el consejo ya está reunido")
        try:
            return svc.council.run()
        finally:
            svc.run_lock.release()

    @router.get("/council/runs", response_model=list[CouncilRun])
    def council_runs():
        return JournalView.load(svc.ctx.journal).runs

    @router.get("/ledger", response_model=list[LedgerEntry])
    def ledger():
        return svc.experiments.ledger()

    @router.get("/veto_regret", response_model=VetoRegret)
    def veto_regret():
        return svc.experiments.veto_regret()

    @router.get("/report", response_model=Report)
    def report():
        return svc.experiments.report()

    return router
