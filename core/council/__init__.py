"""Frente C: consejo y estadística. Dueño: Claude (sesión principal).

`build(ctx)` devuelve el servicio con `.router`, `.start()`, `.stop()` y `.experiments`
(implementa `core.interfaces.ExperimentProvider`).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from core.interfaces import AppContext
from core.llm import OpenAICompatClient

from .council import Council, SeedStore
from .experiments import Experiments
from .journal_view import JournalView
from .routes import make_router

log = logging.getLogger(__name__)
WEEK_MS = 7 * 24 * 3600 * 1000
CHECK_EVERY_S = 1800


def default_client_factory(ctx: AppContext):
    def factory(role: str, model: str) -> OpenAICompatClient:
        cassettes = Path(os.getenv("NDE1_LLM_CASSETTES", ctx.data_dir / "llm_cassettes"))
        return OpenAICompatClient.for_ollama(ctx.settings().ollama_base_url, model, cassette_dir=cassettes)
    return factory


class CouncilService:
    def __init__(self, ctx: AppContext, client_factory=None):
        self.ctx = ctx
        seeds = SeedStore(ctx.data_dir)
        self.council = Council(ctx.journal, ctx.settings, seeds, client_factory or default_client_factory(ctx))
        self.experiments = Experiments(ctx.journal, ctx.settings, seeds)
        self.run_lock = threading.Lock()
        self.router = make_router(self)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def due(self, now_ms: int) -> bool:
        """Reunión semanal: si no hay experimento en curso y pasó una semana desde la última."""
        view = JournalView.load(self.ctx.journal)
        if view.active_prereg() is not None:
            return False
        return not view.runs or now_ms - view.runs[-1].ran_ms >= WEEK_MS

    def _loop(self) -> None:
        while not self._stop.wait(CHECK_EVERY_S):
            try:
                if self.due(int(time.time() * 1000)) and self.run_lock.acquire(blocking=False):
                    try:
                        self.council.run()
                    finally:
                        self.run_lock.release()
            except Exception:                       # el hilo del consejo nunca tumba al núcleo
                log.exception("reunión automática del consejo falló")

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="council-weekly", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


def build(ctx: AppContext, client_factory=None) -> CouncilService:
    return CouncilService(ctx, client_factory)
