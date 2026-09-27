"""Lectura tipada del journal para el consejo. El journal es la única fuente: nada de estado del runtime."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.contracts import (Assignment, BlockConfirmed, BlockOutcome, CouncilRun, Preregistration, Resolution)
from core.journal import Journal


@dataclass
class JournalView:
    blocks: dict[str, BlockConfirmed] = field(default_factory=dict)
    assignments: dict[str, Assignment] = field(default_factory=dict)
    outcomes: dict[str, BlockOutcome] = field(default_factory=dict)      # solo finales, uno por bloque
    aborted: set[str] = field(default_factory=set)
    preregs: list[Preregistration] = field(default_factory=list)
    resolutions: dict[str, Resolution] = field(default_factory=dict)
    runs: list[CouncilRun] = field(default_factory=list)

    @classmethod
    def load(cls, journal: Journal) -> "JournalView":
        v = cls()
        for ev in journal.events():
            k, p = ev["kind"], ev["payload"]
            if k == "block_confirmed":
                v.blocks[p["block_id"]] = BlockConfirmed.model_validate(p)
            elif k == "assignment":
                v.assignments[p["block_id"]] = Assignment.model_validate(p)
            elif k == "outcome" and p["status"] != "pending":
                v.outcomes.setdefault(p["block_id"], BlockOutcome.model_validate(p))
            elif k == "block_abort":
                v.aborted.add(p["block_id"])
            elif k == "preregistration":
                v.preregs.append(Preregistration.model_validate(p))
            elif k == "resolution":
                v.resolutions[p["experiment_id"]] = Resolution.model_validate(p)
            elif k == "council_run":
                v.runs.append(CouncilRun.model_validate(p))
        return v

    def active_prereg(self) -> Preregistration | None:
        open_ = [p for p in self.preregs if p.experiment_id not in self.resolutions]
        return open_[-1] if open_ else None

    def prereg(self, experiment_id: str) -> Preregistration | None:
        return next((p for p in self.preregs if p.experiment_id == experiment_id), None)

    def experiment_outcomes(self, experiment_id: str) -> tuple[list[BlockOutcome], list[BlockOutcome]]:
        """(control, tratamiento) con outcome final, según la asignación sellada."""
        c, t = [], []
        for bid, a in self.assignments.items():
            if a.experiment_id != experiment_id or bid not in self.outcomes:
                continue
            (c if a.arm.value == "control" else t).append(self.outcomes[bid])
        return c, t

    def alpha_history(self) -> list[tuple[float, bool]]:
        """(alpha usado, rechazó) por experimento resuelto, en orden de preregistro."""
        out = []
        for p in self.preregs:
            r = self.resolutions.get(p.experiment_id)
            if r is not None:
                out.append((p.alpha, r.verdict == "supported"))
        return out
