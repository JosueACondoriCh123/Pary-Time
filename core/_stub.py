"""Ayuda de la Fase 0: servicio de frente vacío. Cada frente reemplaza su `build` y deja de usarlo."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException


def not_implemented(front: str):
    raise HTTPException(status_code=501, detail=f"Frente {front}: todavía no implementado")


class StubService:
    def __init__(self, router: APIRouter):
        self.router = router

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
