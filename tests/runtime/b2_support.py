"""Soporte de los tests de B2 (no es conftest para no chocar con B1).

Todo implementa interfaces reales del contrato: `MemoryRepo` es un `BlockRepo` en memoria, `ListActivity` un
`ActivitySource` sobre una lista de tramos, `Recorder` un `ExperimentProvider` que anota lo que recibe. Se usan el
`evaluate_block` y el `categorize` reales del Frente A y un `Journal` real. Los datos son SINTÉTICOS.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.contracts import (ActivitySpan, Arm, Block, BlockOutcome, BlockStatus, Settings, Target, TaskKind,
                            WorkMatcher)
from core.interfaces import AppContext
from core.journal import Journal
from core.runtime.intervention_state import InterventionState
from core.runtime.interventions import NoWindows
from core.runtime.scheduler import Scheduler
from core.sensing.categorize import categorize
from core.sensing.outcome import evaluate_block

P = int(datetime(2026, 9, 29, 9, 0).timestamp() * 1000)
MIN = 60_000


def block(i: int = 1, start: int = P, label: str = "Tesis cap. 3", first_step: str | None = None,
          target: Target | None = None, status: BlockStatus = BlockStatus.confirmed) -> Block:
    return Block(block_id=f"blk_{i:012x}", local_date="2026-09-29", planned_start_ms=start, planned_minutes=50,
                 task_kind=TaskKind.escritura, task_label=label, target=target or Target(kind="none"),
                 work_matchers=[WorkMatcher(field="process", pattern="WINWORD.EXE")], status=status,
                 created_ms=start - 12 * 3600_000, first_step=first_step)


def work(start: int, minutes: float) -> ActivitySpan:
    return ActivitySpan(start_ms=start, end_ms=start + int(minutes * MIN), process="WINWORD.EXE",
                        title="cap3.docx - Word", idle=False)


def distraction(start: int, minutes: float) -> ActivitySpan:
    return ActivitySpan(start_ms=start, end_ms=start + int(minutes * MIN), process="WhatsApp.exe",
                        title="WhatsApp", idle=False)


class MemoryRepo:
    def __init__(self, blocks: list[Block], arms: dict[str, Arm]):
        self.blocks = {b.block_id: b for b in blocks}
        self.arms = arms

    def pending(self) -> list[Block]:
        return [b for b in self.blocks.values() if b.status in (BlockStatus.confirmed, BlockStatus.running)]

    def get(self, block_id: str) -> Block | None:
        return self.blocks.get(block_id)

    def arm(self, block_id: str) -> Arm | None:
        return self.arms.get(block_id)

    def set_status(self, block_id: str, status: BlockStatus) -> None:
        self.blocks[block_id] = self.blocks[block_id].model_copy(update={"status": status})

    def set_aborted(self, block_id: str) -> None:
        self.blocks[block_id] = self.blocks[block_id].model_copy(update={"aborted": True})


class ListActivity:
    def __init__(self, spans: list[ActivitySpan] | None = None):
        self.items = list(spans or [])

    def spans(self, start_ms: int, end_ms: int) -> list[ActivitySpan]:
        out = []
        for s in sorted(self.items, key=lambda x: x.start_ms):
            if s.end_ms > start_ms and s.start_ms < end_ms:
                out.append(s.model_copy(update={"start_ms": max(s.start_ms, start_ms),
                                                "end_ms": min(s.end_ms, end_ms)}))
        return out

    def last_sample_ms(self) -> int | None:
        return max((s.end_ms for s in self.items), default=None)


class Recorder:
    def __init__(self):
        self.outcomes: list[BlockOutcome] = []

    def active(self):
        return None

    def after_outcome(self, outcome: BlockOutcome) -> None:
        self.outcomes.append(outcome)


class RecordingOpener:
    """Reemplaza a os.startfile en pruebas de lógica (abrir Word de verdad no es parte del test)."""

    def __init__(self):
        self.opened: list[str] = []

    def __call__(self, value: str) -> None:
        self.opened.append(value)


def make(tmp_path: Path, blocks: list[Block], arms: dict[str, Arm], spans=None, windows=None, opener=None,
         settings: Settings | None = None):
    s = settings or Settings()
    ctx = AppContext(journal=Journal(tmp_path / "journal.jsonl"), settings=lambda: s, data_dir=tmp_path,
                     activity=ListActivity(spans), evaluate_block=evaluate_block, categorize=categorize,
                     experiments=Recorder())
    repo = MemoryRepo(blocks, arms)
    sched = Scheduler(ctx, repo, InterventionState(tmp_path / "interventions.sqlite"), windows or NoWindows(),
                      opener=opener or RecordingOpener())
    return sched, ctx, repo


def events(ctx: AppContext, kind: str | None = None) -> list[dict]:
    return [e for e in ctx.journal.events() if kind is None or e["kind"] == kind]
