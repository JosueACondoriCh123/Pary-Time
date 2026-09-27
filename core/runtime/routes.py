"""Rutas del Frente B. Las firmas (path, método, modelos) son contrato: no cambiarlas sin pedido."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from core.contracts import (BlockCreate, BlockUpdate, BlockView, ConfirmDay, FirstStep, OverlayState,
                            RuntimeStatus)

from .store import BlockConflict, BlockInvalid, BlockNotFound


def build_router(service) -> APIRouter:
    # Un router por instancia: un segundo núcleo no redirige los datos del primero.
    router = APIRouter(tags=["B: runtime e intervenciones"])

    @router.get("/blocks", response_model=list[BlockView])
    def list_blocks(date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$")):
        return service.list_blocks(date)

    @router.post("/blocks", response_model=BlockView, status_code=201)
    def create_block(body: BlockCreate):
        return service.create_block(body)

    @router.patch("/blocks/{block_id}", response_model=BlockView)
    def update_block(block_id: str, body: BlockUpdate):
        """Solo bloques `planned`; 409 si ya está confirmado."""
        return _call(service.update_block, block_id, body)

    @router.delete("/blocks/{block_id}", response_model=BlockView)
    def cancel_block(block_id: str):
        """Solo bloques `planned` (queda `cancelled`); uno confirmado se aborta, no se cancela."""
        return _call(service.cancel_block, block_id)

    @router.post("/blocks/confirm", response_model=list[BlockView])
    def confirm_day(body: ConfirmDay):
        """Confirma los bloques `planned` del día: sortea y sella las condiciones en el journal."""
        return service.confirm_day(body.local_date)

    @router.post("/blocks/{block_id}/first_step", response_model=BlockView)
    def set_first_step(block_id: str, body: FirstStep):
        return _call(service.set_first_step, block_id, body.text)

    @router.post("/blocks/{block_id}/abort", response_model=BlockView)
    def abort_block(block_id: str):
        """"Hoy no": revierte intervenciones y lo registra. El bloque sigue en el análisis (ITT)."""
        return _call(service.abort_block, block_id)

    @router.get("/runtime/overlay", response_model=OverlayState)
    def overlay():
        return service.overlay()

    @router.get("/runtime/status", response_model=RuntimeStatus)
    def status():
        return service.status()

    @router.post("/runtime/emergency_release", response_model=RuntimeStatus)
    def emergency_release():
        """Salida de emergencia: restaura todas las ventanas minimizadas y no vuelve a minimizar
        en el bloque actual."""
        return service.emergency_release()

    return router


def _call(fn, *args):
    try:
        return fn(*args)
    except BlockNotFound:
        raise HTTPException(status_code=404, detail="bloque inexistente") from None
    except BlockConflict as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from None
    except BlockInvalid:
        raise HTTPException(status_code=422, detail="bloque inválido") from None
