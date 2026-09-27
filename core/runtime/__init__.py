"""Frente B: runtime e intervenciones. B1 (bloques y sorteo): externo 2. B2 (scheduler, intervenciones,
overlay y recuperación): Claude.

Contrato de `build(ctx)`: devuelve un servicio con `.router`, `.start()` y `.stop()`.
La fase 1 guarda bloques, confirma el día y sella `block_confirmed` + `assignment`.
"""
from __future__ import annotations

import secrets
import time

from pydantic import ValidationError

from core.contracts import (Arm, Assignment, Block, BlockConfirmed, BlockCreate, BlockStatus,
                            BlockUpdate, BlockView, permuted_arm)
from core.interfaces import AppContext
from core.journal import append_typed

from .intervention_state import InterventionState
from .interventions import WindowOps, default_window_ops
from .privacy_log import attach_runtime_log, detach_runtime_log
from .routes import build_router
from .scheduler import BlockNotActive, Scheduler
from .store import BlockConflict, BlockInvalid, BlockNotFound, BlockStore, StoredBlock


class StoreRepo:
    """Adapta el `BlockStore` de B1 al protocolo `BlockRepo` del scheduler (B2)."""

    def __init__(self, store: BlockStore):
        self.store = store

    def pending(self) -> list[Block]:
        return [r.block for r in self.store.pending()]

    def get(self, block_id: str) -> Block | None:
        r = self.store.get(block_id)
        return r.block if r else None

    def arm(self, block_id: str) -> Arm | None:
        r = self.store.get(block_id)
        return r.arm if r else None

    def set_status(self, block_id: str, status: BlockStatus) -> None:
        self.store.set_status(block_id, status)

    def set_aborted(self, block_id: str) -> None:
        self.store.set_aborted(block_id)


class SystemClock:
    def now_ms(self) -> int:
        return time.time_ns() // 1_000_000


class RuntimeService:
    def __init__(self, ctx: AppContext, clock: SystemClock | None = None, windows: WindowOps | None = None):
        self.ctx = ctx
        self.clock = clock or SystemClock()
        self.store = BlockStore(ctx.data_dir / "runtime.sqlite")
        self.scheduler = Scheduler(ctx, StoreRepo(self.store),
                                   InterventionState(ctx.data_dir / "interventions.sqlite"),
                                   windows or default_window_ops(), now_ms=self.clock.now_ms)
        self.router = build_router(self)
        self._log: object | None = None

    def start(self) -> None:
        self._log = attach_runtime_log(self.ctx.data_dir)
        self.scheduler.start()              # restaura ventanas de una caída y arranca el tick

    def stop(self) -> None:
        self.scheduler.stop()
        detach_runtime_log(self._log)
        self._log = None
        self.store.close()

    # ---------------------------------------------------------------- B2: rutas de Claude

    def abort_block(self, block_id: str) -> BlockView:
        if self.store.get(block_id) is None:
            raise BlockNotFound()
        try:
            self.scheduler.abort(block_id)
        except BlockNotActive:
            raise BlockConflict("solo se aborta un bloque confirmado que todavía no terminó") from None
        return self._view(self.store.get(block_id))

    def overlay(self):
        return self.scheduler.overlay()

    def status(self):
        return self.scheduler.status()

    def emergency_release(self):
        return self.scheduler.emergency_release()

    def list_blocks(self, local_date: str) -> list[BlockView]:
        return [self._view(record) for record in self.store.list_day(local_date)]

    def create_block(self, body: BlockCreate) -> BlockView:
        block = Block(
            block_id="blk_" + secrets.token_hex(6),
            status=BlockStatus.planned,
            created_ms=self.clock.now_ms(),
            **body.model_dump(),
        )
        return self._view(self.store.insert(block))

    def update_block(self, block_id: str, body: BlockUpdate) -> BlockView:
        with self.store.locked():
            record = self.store.get(block_id)
            if record is None:
                raise BlockNotFound()
            if record.block.status != BlockStatus.planned:
                raise BlockConflict("solo se edita un bloque planned")
            data = record.block.model_dump()
            data.update(body.model_dump(exclude_none=True))
            try:
                block = Block.model_validate(data)
            except ValidationError as exc:
                raise BlockInvalid() from exc
            self.store.replace_planned(block)
            updated = self.store.get(block_id)
        return self._view(updated)

    def cancel_block(self, block_id: str) -> BlockView:
        return self._view(self.store.cancel(block_id))

    def confirm_day(self, local_date: str) -> list[BlockView]:
        with self.store.locked():
            planned = [record for record in self.store.list_day(local_date)
                       if record.block.status == BlockStatus.planned]
            for record in planned:
                self._confirm_one(record.block)
            return [self._view(record) for record in self.store.list_day(local_date)]

    def set_first_step(self, block_id: str, text: str) -> BlockView:
        with self.store.locked():
            record = self.store.get(block_id)
            if record is None:
                raise BlockNotFound()
            if record.arm != Arm.primer_paso:
                raise BlockConflict("el bloque no tiene la intervención primer_paso")
            saved = self.store.set_first_step(block_id, text)
        return self._view(saved)

    def _confirm_one(self, block: Block) -> None:
        confirmed = block.model_copy(update={"status": BlockStatus.confirmed})
        self.store.mark_confirmed(confirmed.block_id)
        append_typed(self.ctx.journal, "block_confirmed", BlockConfirmed(
            block_id=confirmed.block_id,
            local_date=confirmed.local_date,
            planned_start_ms=confirmed.planned_start_ms,
            planned_minutes=confirmed.planned_minutes,
            task_kind=confirmed.task_kind,
        ))
        experiment = self.ctx.experiments.active() if self.ctx.experiments else None
        if experiment is not None and experiment.eligible(confirmed):
            draw_index = _draw_count(self.ctx.journal, experiment.experiment_id)
            arm = permuted_arm(experiment.seed_hex, experiment.experiment_id, draw_index,
                               experiment.treatment)
            experiment_id = experiment.experiment_id
        else:
            arm, experiment_id, draw_index = Arm.control, None, None
        assigned_ms = self.clock.now_ms()
        self.store.save_assignment(confirmed.block_id, arm, experiment_id, draw_index, assigned_ms)
        append_typed(self.ctx.journal, "assignment", Assignment(
            block_id=confirmed.block_id,
            experiment_id=experiment_id,
            arm=arm,
            draw_index=draw_index,
            assigned_ms=assigned_ms,
        ))

    def _view(self, record: StoredBlock) -> BlockView:
        now = self.clock.now_ms()
        revealed = None
        needs_first_step = False
        if record.arm == Arm.primer_paso:
            revealed = record.arm
            needs_first_step = record.block.first_step is None
        elif record.arm is not None and now >= record.block.planned_start_ms:
            revealed = record.arm
        return BlockView(
            **record.block.model_dump(),
            arm_revealed=revealed,
            needs_first_step=needs_first_step,
            experiment_id=record.experiment_id,
        )


def _draw_count(journal, experiment_id: str) -> int:
    return sum(1 for event in journal.events()
               if event["kind"] == "assignment"
               and event["payload"].get("experiment_id") == experiment_id)


def build(ctx: AppContext, clock: SystemClock | None = None, windows: WindowOps | None = None) -> RuntimeService:
    return RuntimeService(ctx, clock, windows)
