"""Rutas del Frente C. Las firmas (path, método, modelos) son contrato."""
from __future__ import annotations

from fastapi import APIRouter

from core._stub import not_implemented
from core.contracts import (CouncilRun, ExperimentProgress, ExperimentRecord, LedgerEntry, Report,
                            VetoRegret)

router = APIRouter(tags=["C: consejo y estadística"])


@router.get("/experiments/current", response_model=ExperimentProgress | None)
def current_experiment():
    """Progreso del experimento en curso, SIN efecto hasta llegar al N. null si no hay."""
    not_implemented("C")


@router.get("/experiments", response_model=list[ExperimentRecord])
def experiments():
    not_implemented("C")


@router.post("/council/run", response_model=CouncilRun)
def run_council():
    """Reunión manual del consejo (además de la semanal automática)."""
    not_implemented("C")


@router.get("/council/runs", response_model=list[CouncilRun])
def council_runs():
    not_implemented("C")


@router.get("/ledger", response_model=list[LedgerEntry])
def ledger():
    not_implemented("C")


@router.get("/veto_regret", response_model=VetoRegret)
def veto_regret():
    not_implemented("C")


@router.get("/report", response_model=Report)
def report():
    not_implemented("C")
