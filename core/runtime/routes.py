"""Rutas del Frente B. Las firmas (path, método, modelos) son contrato: no cambiarlas sin pedido."""
from __future__ import annotations

from fastapi import APIRouter, Query

from core._stub import not_implemented
from core.contracts import (BlockCreate, BlockUpdate, BlockView, ConfirmDay, FirstStep, OverlayState,
                            RuntimeStatus)

router = APIRouter(tags=["B: runtime e intervenciones"])


@router.get("/blocks", response_model=list[BlockView])
def list_blocks(date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$")):
    not_implemented("B")


@router.post("/blocks", response_model=BlockView, status_code=201)
def create_block(body: BlockCreate):
    not_implemented("B")


@router.patch("/blocks/{block_id}", response_model=BlockView)
def update_block(block_id: str, body: BlockUpdate):
    """Solo bloques `planned`; 409 si ya está confirmado."""
    not_implemented("B")


@router.delete("/blocks/{block_id}", response_model=BlockView)
def cancel_block(block_id: str):
    """Solo bloques `planned` (queda `cancelled`); uno confirmado se aborta, no se cancela."""
    not_implemented("B")


@router.post("/blocks/confirm", response_model=list[BlockView])
def confirm_day(body: ConfirmDay):
    """Confirma los bloques `planned` del día: sortea y sella las condiciones en el journal."""
    not_implemented("B")


@router.post("/blocks/{block_id}/first_step", response_model=BlockView)
def set_first_step(block_id: str, body: FirstStep):
    not_implemented("B")


@router.post("/blocks/{block_id}/abort", response_model=BlockView)
def abort_block(block_id: str):
    """"Hoy no": revierte intervenciones y lo registra. El bloque sigue en el análisis (ITT)."""
    not_implemented("B")


@router.get("/runtime/overlay", response_model=OverlayState)
def overlay():
    not_implemented("B")


@router.get("/runtime/status", response_model=RuntimeStatus)
def status():
    not_implemented("B")


@router.post("/runtime/emergency_release", response_model=RuntimeStatus)
def emergency_release():
    """Salida de emergencia: restaura todas las ventanas minimizadas y no vuelve a minimizar
    en el bloque actual."""
    not_implemented("B")
