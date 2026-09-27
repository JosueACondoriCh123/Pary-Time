"""Pure implementation of the frozen outcome@1 rules (all intervals are half-open)."""
from __future__ import annotations

from core.contracts import (
    OUTCOME_RULES, ActivitySpan, Block, BlockOutcome, Category, OutcomeFeatures, Settings,
)

from .categorize import categorize


def evaluate_block(block: Block, spans: list[ActivitySpan], now_ms: int,
                   settings: Settings) -> BlockOutcome:
    planned = block.planned_start_ms
    deadline = planned + OUTCOME_RULES.censor_s * 1000
    required = OUTCOME_RULES.work_run_s * 1000
    tolerance = OUTCOME_RULES.gap_tolerance_s * 1000
    limit = min(now_ms, deadline + required + tolerance)
    observed: list[ActivitySpan] = []
    early = False
    for span in sorted(spans, key=lambda s: (s.start_ms, s.end_ms)):
        start, end = max(planned, span.start_ms), min(limit, span.end_ms)
        if end <= start:
            continue
        if observed and start < observed[-1].end_ms:
            raise ValueError("activity spans must not overlap")
        observed.append(span.model_copy(update={"start_ms": start, "end_ms": end}))
        if (span.start_ms <= planned < span.end_ms and not span.idle and not span.locked
                and categorize(span, block, settings) == Category.work):
            early = True

    run_start: int | None = None
    run_end: int | None = None
    qualified: int | None = None
    for span in observed:
        if span.idle or span.locked or categorize(span, block, settings) != Category.work:
            continue
        if run_end is None or span.start_ms - run_end >= tolerance:
            run_start = span.start_ms
        run_end = span.end_ms
        if run_start < deadline and run_end - run_start >= required:
            qualified = run_start
            break

    present = any(s.start_ms < deadline for s in observed)
    open_run = (run_start is not None and run_start < deadline and run_end is not None
                and now_ms - run_end < tolerance)
    if qualified is not None:
        status = "started"
    elif now_ms >= deadline and not present:
        status = "device_off"
    elif now_ms >= deadline and not open_run:
        status = "censored"
    else:
        status = "pending"

    feature_end = qualified if qualified is not None else deadline
    before = [s.model_copy(update={"end_ms": min(s.end_ms, feature_end)})
              for s in observed if s.start_ms < feature_end]
    duration = feature_end - planned
    coverage_ms = sum(s.end_ms - s.start_ms for s in before)
    distraction_ms = sum(s.end_ms - s.start_ms for s in before
                         if categorize(s, block, settings) == Category.distraction)
    features = OutcomeFeatures(
        pre_start_switches=sum(a.process != b.process for a, b in zip(before, before[1:])),
        first_category=categorize(observed[0], block, settings) if observed else Category.none,
        distraction_s_before_start=distraction_ms // 1000,
        sensor_coverage=coverage_ms / duration if duration else 1.0,
        started_early=qualified == planned and early,
    )
    return BlockOutcome(
        block_id=block.block_id, status=status,
        latency_s=(qualified - planned) / 1000 if qualified is not None else None,
        censored=status == "censored", work_run_start_ms=qualified,
        features=features, rules_version=OUTCOME_RULES.rules_version, computed_ms=now_ms,
    )
