"""Experimentos: `ExperimentProvider` para el runtime, resolución al llegar al N y vistas de solo lectura.

El progreso que se expone NUNCA incluye el efecto antes de la `resolution` (anti-espiar).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from core.contracts import (BlockOutcome, ExperimentProgress, ExperimentRecord, JournalVerify, LedgerEntry,
                            Report, Resolution, Settings, VetoRegret, permuted_arm, seed_commitment)
from core.council.council import SeedStore
from core.council.journal_view import JournalView
from core.interfaces import ActiveExperiment
from core.journal import Journal, JournalError, append_typed
from core.stats.analysis import analyze
from core.stats.ledger import build_ledger

log = logging.getLogger(__name__)


class ExperimentError(RuntimeError):
    pass


class Experiments:
    """Implementa `core.interfaces.ExperimentProvider`."""

    def __init__(self, journal: Journal, settings: Callable[[], Settings], seeds: SeedStore,
                 now_ms: Callable[[], int] = lambda: int(time.time() * 1000)):
        self.journal, self.settings, self.seeds, self.now_ms = journal, settings, seeds, now_ms
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- ExperimentProvider

    def active(self) -> ActiveExperiment | None:
        p = JournalView.load(self.journal).active_prereg()
        if p is None:
            return None
        seed = self.seeds.load(p.experiment_id)
        if seed is None or seed_commitment(seed) != p.seed_commitment:
            # Sin la semilla comprometida no se puede sortear de forma verificable: el runtime asigna
            # control (línea base) y queda el error en el log, en vez de romper la confirmación del día.
            log.error("semilla de %s ausente o no coincide con el compromiso", p.experiment_id)
            return None
        return ActiveExperiment(p.experiment_id, p.hypothesis.intervention, p.hypothesis.moderator,
                                p.n_per_arm, seed)

    def after_outcome(self, outcome: BlockOutcome) -> None:
        with self._lock:
            view = JournalView.load(self.journal)
            p = view.active_prereg()
            a = view.assignments.get(outcome.block_id)
            if p is None or a is None or a.experiment_id != p.experiment_id:
                return
            c, t = view.experiment_outcomes(p.experiment_id)
            usable = lambda xs: sum(o.status in ("started", "censored") for o in xs)  # noqa: E731
            if usable(c) >= p.n_per_arm and usable(t) >= p.n_per_arm:
                self._resolve(view, p.experiment_id)

    # ---------------------------------------------------------------- resolución

    def _resolve(self, view: JournalView, experiment_id: str) -> Resolution:
        p = view.prereg(experiment_id)
        seed = self.seeds.load(experiment_id)
        if seed is None or seed_commitment(seed) != p.seed_commitment:
            raise ExperimentError(f"no se puede revelar la semilla de {experiment_id}")
        self._check_draws(view, experiment_id, seed, p.arms[1])
        c, t = view.experiment_outcomes(experiment_id)
        an = analyze(c, t, n_per_arm=p.n_per_arm, alpha=p.alpha, experiment_id=experiment_id,
                     rules=p.outcome_rules)
        in_exp = {bid for bid, a in view.assignments.items() if a.experiment_id == experiment_id}
        res = Resolution(experiment_id=experiment_id, resolved_ms=self.now_ms(), verdict=an.verdict,
                         n_control=an.n_control, n_treatment=an.n_treatment, median_control_s=an.median_control_s,
                         median_treatment_s=an.median_treatment_s, ratio=an.ratio, p_value=an.p_value,
                         alpha=p.alpha, censored_control=an.censored_control,
                         censored_treatment=an.censored_treatment, excluded_device_off=an.excluded_device_off,
                         aborted_blocks=len(in_exp & view.aborted), seed_revealed=seed)
        append_typed(self.journal, "resolution", res)
        return res

    @staticmethod
    def _check_draws(view: JournalView, experiment_id: str, seed: str, treatment) -> None:
        """Invariante del journal: cada asignación coincide con el sorteo de referencia."""
        for a in view.assignments.values():
            if a.experiment_id != experiment_id:
                continue
            expected = permuted_arm(seed, experiment_id, a.draw_index, treatment)
            if a.arm != expected:
                raise ExperimentError(f"{a.block_id}: asignado {a.arm.value}, el sorteo dice {expected.value}")

    # ---------------------------------------------------------------- vistas

    def progress(self) -> ExperimentProgress | None:
        view = JournalView.load(self.journal)
        p = view.active_prereg()
        if p is None:
            return None
        c, t = view.experiment_outcomes(p.experiment_id)
        done = lambda xs: sum(o.status in ("started", "censored") for o in xs)  # noqa: E731
        return ExperimentProgress(experiment_id=p.experiment_id, intervention=p.hypothesis.intervention,
                                  moderator=p.hypothesis.moderator, n_per_arm=p.n_per_arm,
                                  n_control_done=done(c), n_treatment_done=done(t), status="running",
                                  created_ms=p.created_ms)

    def records(self) -> list[ExperimentRecord]:
        view = JournalView.load(self.journal)
        return [ExperimentRecord(preregistration=p, resolution=view.resolutions.get(p.experiment_id))
                for p in view.preregs]

    def ledger(self) -> list[LedgerEntry]:
        view = JournalView.load(self.journal)
        return build_ledger((p.hypothesis.intervention, view.resolutions[p.experiment_id].verdict)
                            for p in view.preregs if p.experiment_id in view.resolutions)

    def veto_regret(self) -> VetoRegret:
        items = [r for r in self.records() if r.preregistration.source == "exploration_vetoed"
                 and r.resolution is not None]
        return VetoRegret(n_explored=len(items), n_replicated=sum(r.resolution.verdict == "supported" for r in items),
                          items=items)

    def report(self) -> Report:
        try:
            jv = JournalVerify(ok=True, n_events=self.journal.verify())
        except JournalError as e:
            jv = JournalVerify(ok=False, n_events=0, error=str(e))
        return Report(generated_ms=self.now_ms(), journal=jv, experiments=self.records(), ledger=self.ledger(),
                      veto_regret=self.veto_regret())
