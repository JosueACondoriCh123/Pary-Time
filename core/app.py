"""Composición del núcleo (Frente 0). Arma el grafo de frentes y monta sus rutas.

Nadie más edita este archivo: un frente expone `build(ctx)` en su paquete y acá se conecta.
"""
from __future__ import annotations

import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core import council, runtime, sensing
from core.contracts import CONTRACTS_VERSION, Health, JournalVerify, Settings
from core.interfaces import AppContext
from core.journal import AGENT_VERSION, Journal, JournalError, LoopLock, append_typed

TOKEN_HEADER = "X-NDE1-Token"


class SettingsStore:
    def __init__(self, path: Path):
        self.path = path
        self._cache: Settings | None = None

    def get(self) -> Settings:
        if self._cache is None:
            try:
                self._cache = Settings.model_validate_json(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                self._cache = Settings()
        return self._cache

    def put(self, new: Settings) -> list[str]:
        old = self.get().model_dump()
        changed = sorted(k for k, v in new.model_dump().items() if old.get(k) != v)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(new.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self._cache = new
        return changed


def create_app(data_dir: Path, token: str | None = None) -> FastAPI:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    token = token or secrets.token_urlsafe(32)
    journal = Journal(data_dir / "journal.jsonl")
    store = SettingsStore(data_dir / "settings.json")
    lock = LoopLock(data_dir / "core.lock")

    ctx = AppContext(journal=journal, settings=store.get, data_dir=data_dir)
    s_a = sensing.build(ctx)
    ctx.activity, ctx.evaluate_block, ctx.categorize = s_a.activity, s_a.evaluate_block, s_a.categorize
    s_c = council.build(ctx)
    ctx.experiments = s_c.experiments
    s_b = runtime.build(ctx)
    services = [s_a, s_c, s_b]            # arranque en este orden, parada al revés

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        lock.acquire()                    # un solo escritor por journal
        try:
            append_typed(journal, "app_start", {"version": AGENT_VERSION, "contracts": CONTRACTS_VERSION})
            for s in services:
                s.start()
            yield
        finally:
            for s in reversed(services):
                s.stop()
            lock.release()

    app = FastAPI(title="Consejo N-de-1", version=AGENT_VERSION, lifespan=lifespan)
    app.state.ctx, app.state.token = ctx, token
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                       allow_headers=[TOKEN_HEADER, "Content-Type"])

    def auth(x_nde1_token: str = Header(default="", alias=TOKEN_HEADER)):
        if not secrets.compare_digest(x_nde1_token, token):
            raise HTTPException(status_code=401, detail="token local inválido")

    @app.get("/health", response_model=Health, tags=["0: columna"])
    def health():
        last = None
        for last in journal.events():
            pass
        return Health(ok=True, version=AGENT_VERSION, contracts=CONTRACTS_VERSION,
                      journal_seq=last["seq"] if last else 0)

    guarded = [Depends(auth)]

    @app.get("/journal/verify", response_model=JournalVerify, dependencies=guarded, tags=["0: columna"])
    def journal_verify():
        try:
            return JournalVerify(ok=True, n_events=journal.verify())
        except JournalError as e:
            return JournalVerify(ok=False, n_events=0, error=str(e))

    @app.get("/settings", response_model=Settings, dependencies=guarded, tags=["0: columna"])
    def get_settings():
        return store.get()

    @app.put("/settings", response_model=Settings, dependencies=guarded, tags=["0: columna"])
    def put_settings(body: Settings):
        changed = store.put(body)
        if changed:
            append_typed(journal, "settings_changed", {"keys": changed})
        return body

    for s in services:
        app.include_router(s.router, dependencies=guarded)
    return app


def ready_line(port: int) -> str:
    """Única línea que Electron espera por stdout para saber que el núcleo está listo."""
    return "NDE1_READY " + json.dumps({"port": port, "version": AGENT_VERSION, "contracts": CONTRACTS_VERSION})
