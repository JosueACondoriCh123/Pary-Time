"""Scheduler de B2: el ciclo de vida de cada bloque confirmado.

Por tick (unos 2 s):
  1. Un bloque confirmado cuya hora llegó pasa a `running`.
  2. Solo el bloque más reciente dentro de su ventana [P, P + censor) tiene intervención activa. Si la compu
     despertó tarde dentro de la ventana, se aplica con `device_wake`. Si otro bloque toma la posta, el anterior
     se revierte (`block_start`); fuera de ventana, `censor`.
  3. Se evalúa con `evaluate_block` (Frente A) sobre todo el intervalo normativo. Cuando el resultado es final:
     revertir → outcome al journal → estado → `experiments.after_outcome` (Frente C).
  4. `retrasar_distracciones` vuelve a minimizar lo que reaparece (`reapplied`), salvo tras la salida de emergencia.

Constitución en código: nunca se interviene fuera de un bloque confirmado y en ventana, la lista blanca nunca se
toca, una sola intervención activa a la vez, abortar siempre es posible y el bloque abortado se sigue evaluando
(intención de tratar).

Del store de bloques (B1) solo se usa el protocolo `BlockRepo`.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Protocol

from core.contracts import (INTERVENTIONS, OUTCOME_RULES, Arm, Block, BlockAbort, BlockOutcome,
                            BlockStatus, InterventionEvent, OverlayState, RuntimeStatus)
from core.interfaces import AppContext
from core.journal import append_typed
from core.runtime.intervention_state import InterventionState
from core.runtime.interventions import Opener, WindowOps, open_target, select_distractions
from core.runtime.overlay import (COUNTDOWN_LEAD_MS, HIDDEN, WORK_STREAK_TO_HIDE_S, overlay_for,
                                  work_streak_s)

log = logging.getLogger(__name__)

TICK_S = 2.0
WAKE_GAP_MS = 30_000          # ver un bloque por primera vez más de 30 s después de P = device_wake
EVAL_SPAN_MS = (OUTCOME_RULES.censor_s + OUTCOME_RULES.work_run_s + OUTCOME_RULES.gap_tolerance_s) * 1000
WINDOW_MS = OUTCOME_RULES.censor_s * 1000
PENDING = (BlockStatus.confirmed, BlockStatus.running)


class BlockRepo(Protocol):
    """Lo mínimo que B2 necesita del store de bloques de B1."""

    def pending(self) -> list[Block]:
        """Bloques `confirmed` o `running`, cualquier fecha."""
        ...

    def get(self, block_id: str) -> Block | None: ...

    def arm(self, block_id: str) -> Arm | None:
        """Condición sorteada (None si el bloque no tiene asignación)."""
        ...

    def set_status(self, block_id: str, status: BlockStatus) -> None: ...

    def set_aborted(self, block_id: str) -> None: ...


class BlockNotActive(Exception):
    """El bloque no existe o ya no se puede abortar (409 / 404 en la ruta)."""


class Scheduler:
    def __init__(self, ctx: AppContext, repo: BlockRepo, state: InterventionState, windows: WindowOps,
                 now_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000, opener: Opener | None = None):
        self.ctx, self.repo, self.state, self.win = ctx, repo, state, windows
        self.now_ms, self.opener = now_ms, opener
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._warned_no_eval = False

    # ---------------------------------------------------------------- ciclo

    def start(self) -> None:
        self.recover()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="runtime-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:                                  # el scheduler nunca tumba al núcleo
                log.exception("tick del scheduler falló")
            self._stop.wait(TICK_S)

    def tick(self, now: int | None = None) -> None:
        now = self.now_ms() if now is None else now
        with self._lock:
            blocks = sorted(self.repo.pending(), key=lambda b: b.planned_start_ms)
            started = [b for b in blocks if b.planned_start_ms <= now]
            in_window = [b for b in started if now < b.planned_start_ms + WINDOW_MS]
            active_id = in_window[-1].block_id if in_window else None
            for b in started:
                if b.status == BlockStatus.confirmed:
                    self.repo.set_status(b.block_id, BlockStatus.running)
                    b = b.model_copy(update={"status": BlockStatus.running})
                arm = self.repo.arm(b.block_id) or Arm.control
                self._drive_intervention(b, arm, now, is_active=b.block_id == active_id)
                self._evaluate(b, arm, now)

    # ---------------------------------------------------------------- intervenciones

    def _drive_intervention(self, b: Block, arm: Arm, now: int, *, is_active: bool) -> None:
        if arm not in INTERVENTIONS:
            return
        phase = self.state.phase(b.block_id)
        if is_active and not b.aborted:
            if phase is None:
                # Con el núcleo corriendo, el primer tick después de P llega en ~2 s. Verlo por primera vez
                # más tarde significa compu apagada/dormida o núcleo caído: se aplica igual, dentro de ventana.
                late = now - b.planned_start_ms > WAKE_GAP_MS
                self._apply(b, arm, now, "device_wake" if late else "block_start")
            elif arm == Arm.retrasar_distracciones and phase in ("applied", "recovered") \
                    and not self.state.emergency(b.block_id):
                self._reminimize(b, now, first=phase == "recovered")
        elif phase == "applied":
            in_window = now < b.planned_start_ms + WINDOW_MS
            self._revert(b, arm, now, "block_start" if in_window else "censor")

    def _event(self, b: Block, arm: Arm, action: str, reason: str, now: int, n: int = 0) -> None:
        append_typed(self.ctx.journal, "intervention",
                     InterventionEvent(block_id=b.block_id, arm=arm, action=action, reason=reason, n_windows=n,
                                       ts_ms=now))

    def _apply(self, b: Block, arm: Arm, now: int, reason: str) -> None:
        if arm == Arm.abrir_trabajo:
            err = open_target(b.target, self.opener)
            if err:
                log.warning("abrir_trabajo en %s: %s", b.block_id, err)
                self.state.mark_applied(b.block_id, arm.value, now)
                self.state.mark_reverted(b.block_id, now)            # no reintentar en cada tick
                self._event(b, arm, "failed", "error", now)
                return
            self.state.mark_applied(b.block_id, arm.value, now)
            self._event(b, arm, "applied", reason, now)
            return
        if arm == Arm.retrasar_distracciones:
            if self.ctx.categorize is None:
                self.state.mark_applied(b.block_id, arm.value, now)
                self.state.mark_reverted(b.block_id, now)
                self._event(b, arm, "failed", "error", now)
                return
            self.state.mark_applied(b.block_id, arm.value, now)
            n = self._minimize_new(b)
            self._event(b, arm, "applied", reason, now, n)
            return
        self.state.mark_applied(b.block_id, arm.value, now)          # primer_paso / cuenta_regresiva: overlay
        self._event(b, arm, "applied", reason, now)

    def _minimize_new(self, b: Block) -> int:
        n = 0
        for w in select_distractions(self.win.windows(), self.ctx.settings(), self.ctx.categorize):
            if self.win.minimize(w.hwnd):
                self.state.add_minimized(b.block_id, w.hwnd, w.process)
                n += 1
        return n

    def _reminimize(self, b: Block, now: int, *, first: bool) -> None:
        if first:
            self.state.mark_applied(b.block_id, Arm.retrasar_distracciones.value, now)
        n = self._minimize_new(b)
        if n or first:
            self._event(b, Arm.retrasar_distracciones, "reapplied", "recovery" if first else "block_start", now, n)

    def _restore_windows(self, block_id: str) -> int:
        n = sum(self.win.restore(h) for h in self.state.minimized(block_id))
        self.state.mark_restored(block_id)
        return n

    def _revert(self, b: Block, arm: Arm, now: int, reason: str) -> None:
        n = self._restore_windows(b.block_id) if arm == Arm.retrasar_distracciones else 0
        self.state.mark_reverted(b.block_id, now)
        self.state.set_overlay_done(b.block_id)
        self._event(b, arm, "reverted", reason, now, n)

    # ---------------------------------------------------------------- evaluación

    def _evaluate(self, b: Block, arm: Arm, now: int) -> None:
        if self.ctx.activity is None or self.ctx.evaluate_block is None:
            if not self._warned_no_eval:
                log.warning("sin sensor: no se evalúan outcomes (Frente A no conectado)")
                self._warned_no_eval = True
            return
        P = b.planned_start_ms
        spans = self.ctx.activity.spans(P, min(now, P + EVAL_SPAN_MS) + 1)
        outcome = self.ctx.evaluate_block(b, spans, now, self.ctx.settings())
        if outcome.status != "pending":
            self._finalize(b, arm, outcome, now)

    def _finalize(self, b: Block, arm: Arm, outcome: BlockOutcome, now: int) -> None:
        if self.state.phase(b.block_id) == "applied":
            self._revert(b, arm, now, "work_run_reached" if outcome.status == "started" else "censor")
        if not self._outcome_journaled(b.block_id):
            append_typed(self.ctx.journal, "outcome", outcome)
        self.repo.set_status(b.block_id, BlockStatus(outcome.status))
        self.state.set_overlay_done(b.block_id)
        if self.ctx.experiments is not None:
            try:
                self.ctx.experiments.after_outcome(outcome)
            except Exception:                                  # el consejo no puede frenar al runtime
                log.exception("after_outcome falló para %s", b.block_id)

    def _outcome_journaled(self, block_id: str) -> bool:
        return any(e["kind"] == "outcome" and e["payload"]["block_id"] == block_id
                   and e["payload"]["status"] != "pending" for e in self.ctx.journal.events())

    # ---------------------------------------------------------------- recuperación, abort, emergencia

    def recover(self, now: int | None = None) -> int:
        """Restaura todo lo aplicado y no revertido (caída del núcleo). Devuelve cuántos bloques."""
        now = self.now_ms() if now is None else now
        with self._lock:
            rows = self.state.unreverted()
            for block_id, arm in rows:
                n = self._restore_windows(block_id)
                self.state.mark_reverted(block_id, now, phase="recovered")
                append_typed(self.ctx.journal, "intervention",
                             InterventionEvent(block_id=block_id, arm=Arm(arm), action="reverted",
                                               reason="recovery", n_windows=n, ts_ms=now))
            return len(rows)

    def abort(self, block_id: str, now: int | None = None) -> Block:
        now = self.now_ms() if now is None else now
        with self._lock:
            b = self.repo.get(block_id)
            if b is None or b.status not in PENDING or b.aborted:
                raise BlockNotActive(block_id)
            arm = self.repo.arm(block_id) or Arm.control
            if self.state.phase(block_id) == "applied":
                self._revert(b, arm, now, "abort")
            self.repo.set_aborted(block_id)
            self.state.set_overlay_done(block_id)
            append_typed(self.ctx.journal, "block_abort", BlockAbort(block_id=block_id, ts_ms=now))
            return self.repo.get(block_id)

    def emergency_release(self, now: int | None = None) -> RuntimeStatus:
        now = self.now_ms() if now is None else now
        with self._lock:
            for b in self.repo.pending():
                arm = self.repo.arm(b.block_id) or Arm.control
                if b.planned_start_ms <= now + COUNTDOWN_LEAD_MS:
                    self.state.set_emergency(b.block_id)
                    self.state.set_overlay_done(b.block_id)
                if self.state.phase(b.block_id) in ("applied", "recovered") and arm in INTERVENTIONS:
                    n = self._restore_windows(b.block_id)
                    self.state.mark_reverted(b.block_id, now)
                    self._event(b, arm, "reverted", "emergency_release", now, n)
            return self.status(now)

    # ---------------------------------------------------------------- vistas

    def _active(self, now: int) -> Block | None:
        live = [b for b in self.repo.pending() if b.planned_start_ms <= now < b.planned_start_ms + WINDOW_MS]
        return max(live, key=lambda b: b.planned_start_ms) if live else None

    def overlay(self, now: int | None = None) -> OverlayState:
        now = self.now_ms() if now is None else now
        with self._lock:
            soon = [b for b in self.repo.pending()
                    if b.planned_start_ms - COUNTDOWN_LEAD_MS <= now < b.planned_start_ms + WINDOW_MS]
            if not soon:
                return HIDDEN
            b = max(soon, key=lambda x: x.planned_start_ms)
            arm = self.repo.arm(b.block_id) or Arm.control
            hidden = self.state.overlay_done(b.block_id) or self.state.emergency(b.block_id)
            if not hidden and now >= b.planned_start_ms and self.ctx.activity and self.ctx.categorize:
                spans = self.ctx.activity.spans(now - 600_000, now + 1)
                if work_streak_s(spans, b, self.ctx.settings(), self.ctx.categorize, now) >= WORK_STREAK_TO_HIDE_S:
                    self.state.set_overlay_done(b.block_id)
                    hidden = True
            return overlay_for(b, arm, now, hidden=hidden)

    def status(self, now: int | None = None) -> RuntimeStatus:
        now = self.now_ms() if now is None else now
        with self._lock:
            active = self._active(now)
            arm = (self.repo.arm(active.block_id) or Arm.control) if active else None
            applied = [arm] if active and arm in INTERVENTIONS and self.state.phase(active.block_id) == "applied" else []
            upcoming = [b.planned_start_ms for b in self.repo.pending() if b.planned_start_ms > now]
            return RuntimeStatus(active_block_id=active.block_id if active else None, active_arm_revealed=arm,
                                 interventions_applied=applied, next_block_start_ms=min(upcoming, default=None),
                                 emergency_released=bool(active and self.state.emergency(active.block_id)))
