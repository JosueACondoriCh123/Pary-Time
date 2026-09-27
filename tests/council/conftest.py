"""Fixtures del consejo.

`baseline_journal` escribe una línea base SINTÉTICA (no es evidencia de nadie) con los modelos reales del
contrato y `append_typed`, igual que lo haría el runtime: mañanas lentas que arrancan en distracción,
tardes más rápidas. Fechas fijas, así el snapshot (y la clave de cassette del LLM) es reproducible.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from core.contracts import (Arm, Assignment, BlockConfirmed, BlockOutcome, Category, OutcomeFeatures, Settings,
                            TaskKind)
from core.journal import Journal, append_typed

BASE_DAY = datetime(2026, 9, 14)            # lunes


def write_block(j: Journal, i: int, start: datetime, kind, latency_s: float | None, first,
                arm: Arm = Arm.control, experiment_id: str | None = None,
                draw_index: int | None = None, status: str | None = None) -> str:
    bid = f"blk_{i:012x}"
    ms = int(start.timestamp() * 1000)
    first = Category(first)
    append_typed(j, "block_confirmed", BlockConfirmed(block_id=bid, local_date=start.date().isoformat(),
                                                      planned_start_ms=ms, planned_minutes=50,
                                                      task_kind=TaskKind(kind)))
    append_typed(j, "assignment", Assignment(block_id=bid, experiment_id=experiment_id, arm=arm,
                                             draw_index=draw_index, assigned_ms=ms - 36_000_000))
    st = status or ("censored" if latency_s is None else "started")
    feats = None if st == "device_off" else OutcomeFeatures(
        pre_start_switches=3 if first == Category.distraction else 1, first_category=first,
        distraction_s_before_start=int(min(latency_s or 5400, 5400) * (0.7 if first == Category.distraction else 0.1)),
        sensor_coverage=1.0, started_early=False)
    append_typed(j, "outcome", BlockOutcome(block_id=bid, status=st, latency_s=latency_s if st == "started" else None,
                                            censored=st == "censored", work_run_start_ms=None, features=feats,
                                            computed_ms=ms + 6_000_000))
    return bid


def fill_baseline(j: Journal, days: int = 12, seed: int = 3) -> list[str]:
    rng = np.random.default_rng(seed)
    ids, i = [], 0
    for d in range(days):
        day = BASE_DAY + timedelta(days=d)
        for hour, med, kind in ((9, 1500, TaskKind.escritura), (15, 500, TaskKind.lectura)):
            lat = float(np.exp(rng.normal(np.log(med + 60), 0.5)) - 60)
            lat = None if lat > 5400 else round(max(lat, 0), 1)
            first = Category.distraction if hour == 9 and rng.random() < 0.8 else Category.other
            ids.append(write_block(j, i, day.replace(hour=hour), kind if d % 3 else TaskKind.estudio, lat, first))
            i += 1
    return ids


@pytest.fixture
def journal(tmp_path):
    return Journal(tmp_path / "journal.jsonl")


@pytest.fixture
def baseline(journal):
    fill_baseline(journal)
    return journal


@pytest.fixture
def settings():
    return Settings()
