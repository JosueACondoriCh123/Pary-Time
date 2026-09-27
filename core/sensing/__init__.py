"""Frente A: Windows activity source, pure outcome evaluation and private summaries."""
from __future__ import annotations

import time
from datetime import date, datetime

from fastapi import HTTPException

from core.contracts import ActivitySummary, BlockConfirmed, BlockOutcome, Category
from core.interfaces import AppContext

from .categorize import categorize
from .outcome import evaluate_block
from .routes import build_router
from .sampler import Sampler
from .store import SpanStore


class SensingService:
    evaluate_block = staticmethod(evaluate_block)
    categorize = staticmethod(categorize)

    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.activity = SpanStore(ctx.data_dir / "activity.sqlite")
        self.sampler = Sampler(self.activity, ctx.settings)
        self.router = build_router(self)

    def start(self) -> None:
        self.sampler.start()

    def stop(self) -> None:
        self.sampler.stop()
        self.activity.close()

    def summary(self, now_ms: int | None = None) -> ActivitySummary:
        now_ms = time.time_ns() // 1_000_000 if now_ms is None else now_ms
        local = datetime.fromtimestamp(now_ms / 1000)
        start_ms = int(local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        totals = dict.fromkeys(("distraction", "other", "idle", "paused"), 0)
        settings = self.ctx.settings()
        for span in self.activity.spans(start_ms, now_ms):
            if span.process == "__paused__":
                category = "paused"
            elif span.idle or span.locked:
                category = "idle"
            elif categorize(span, None, settings) == Category.distraction:
                category = "distraction"
            else:
                category = "other"
            totals[category] += span.end_ms - span.start_ms
        return ActivitySummary(local_date=local.date().isoformat(),
                               minutes_by_category={k: v // 60000 for k, v in totals.items()},
                               sensor_running=self.sampler.running,
                               paused_until_ms=self.sampler.paused_until_ms)

    def outcomes(self, from_date: str, to_date: str) -> list[BlockOutcome]:
        try:
            start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="fecha local inválida") from None
        if start > end:
            raise HTTPException(status_code=422, detail="from_date debe ser anterior o igual a to_date")
        events = list(self.ctx.journal.events())
        dates = {item.block_id: item.local_date for event in events if event["kind"] == "block_confirmed"
                 for item in [BlockConfirmed.model_validate(event["payload"])]}
        return [item for event in events if event["kind"] == "outcome"
                for item in [BlockOutcome.model_validate(event["payload"])]
                if item.status != "pending" and from_date <= dates.get(item.block_id, "") <= to_date]


def build(ctx: AppContext) -> SensingService:
    return SensingService(ctx)
