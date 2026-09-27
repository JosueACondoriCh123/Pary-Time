"""SYNTHETIC demo observations, never evidence about a person or treatment.

Only the supplied Random advances. No wall clock, files, native sensor or journal.
Use synthetic Blocks: work matchers are supplied demo vocabulary. Never pass real
user blocks. Labels, targets and first-step text are never copied into the trace.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta
from random import Random

from core.contracts import OUTCOME_RULES, ActivitySpan, Block, Category, Settings
from core.sensing.categorize import categorize


_WINDOW_S = (OUTCOME_RULES.censor_s + OUTCOME_RULES.work_run_s
             + OUTCOME_RULES.gap_tolerance_s)
_DISTRACTIONS = (("chrome.exe", "YouTube - Google Chrome"), ("WhatsApp.exe", "WhatsApp"),
                 ("Discord.exe", ""), ("Telegram.exe", ""))


def _span(start: int, end: int, process: str, title: str = "", *,
          idle: bool = False, locked: bool = False) -> ActivitySpan:
    return ActivitySpan(start_ms=start, end_ms=end, process=process, title=title,
                        idle=idle, locked=locked)


def _windows(block: Block) -> tuple[tuple[str, str], list[tuple[str, str]]]:
    settings = Settings()
    matcher = next((m for m in block.work_matchers if m.field == "process"), block.work_matchers[0])
    # This catches obvious private values; it cannot establish provenance. Callers
    # must construct synthetic matchers, as required by the demo-only interface.
    if re.search(r"[\\/@\r\n]|[A-Za-z]:", matcher.pattern):
        raise ValueError("use generic synthetic work matchers without paths or emails")
    work = ((matcher.pattern, "synthetic work") if matcher.field == "process"
            else ("notepad.exe", "synthetic work - " + matcher.pattern))
    distractions = [window for window in _DISTRACTIONS
                    if categorize(_span(0, 1, *window), block, settings) == Category.distraction]
    if (not distractions or
            categorize(_span(0, 1, *work), block, settings) != Category.work):
        raise ValueError("synthetic blocks need supported work and distraction matchers")
    return work, distractions


def synth_day(day: date, blocks: list[Block], profile: str, rng: Random,
              latency_scale: dict[str, float] | None = None) -> list[ActivitySpan]:
    """Generate ordered nonoverlapping spans around blocks of one LOCAL day.

    Pass random.Random(seed) explicitly. Supported profile: tdah_mananas. Morning
    baseline delay medians are 25 min, afternoon/evening 8, with sigma_log=0.6.
    Per block: 5% off. Morning blocks have an extra 10% long-delay component
    (95–130 min); ordinary lognormal tails can also cross the censor threshold.
    80% of mornings start in distraction; 1–4 window changes precede work.
    These are invented demo parameters, not clinical estimates. Missing spans mean
    off; __paused__ with an empty title means privacy pause. Some trailing periods
    are idle/locked. Background daytime activity includes occasional privacy pauses.

    Scale multiplies latent delay (including long delays) before outcome@1 applies.
    It does not change device-off probability. Zero means an immediate work start.
    Unlisted blocks use 1.0. A child RNG per block keeps later draws identical when
    only scales change. Reproducibility also requires the same local timezone.

    Windows reserve 106 min from P (censor + required work + gap tolerance). Reject
    overlap, midnight crossing and unsupported matchers instead of inventing data.
    Input order is immaterial; all validation happens before advancing rng.
    """
    if type(day) is not date or profile != "tdah_mananas" or not isinstance(rng, Random):
        raise ValueError("expected a date, tdah_mananas profile and seeded random.Random")
    ordered = sorted(blocks, key=lambda b: (b.planned_start_ms, b.block_id))
    ids = {block.block_id for block in ordered}
    if len(ids) != len(ordered):
        raise ValueError("duplicate synthetic block")
    scales = latency_scale or {}
    if any(key not in ids for key in scales):
        raise ValueError("latency_scale contains an unknown block")
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) or value < 0 for value in scales.values()):
        raise ValueError("latency scales must be finite nonnegative numbers")
    day_start = int(datetime.combine(day, time.min).timestamp() * 1000)
    day_end = int(datetime.combine(day + timedelta(days=1), time.min).timestamp() * 1000)
    previous_end = day_start
    windows = []
    for block in ordered:
        start = block.planned_start_ms
        end = start + _WINDOW_S * 1000
        if (block.local_date != day.isoformat() or start < previous_end or end > day_end):
            raise ValueError("synthetic observation windows must be separate and within day")
        windows.append(_windows(block))
        previous_end = end

    result: list[ActivitySpan] = []
    for block, (work, distractions) in zip(ordered, windows):
        local_rng = Random(rng.getrandbits(128))
        scenario = local_rng.random()
        hour = datetime.fromtimestamp(block.planned_start_ms / 1000).hour
        morning = hour < 12
        delay = local_rng.lognormvariate(math.log((25 if morning else 8) * 60), .6)
        if morning and local_rng.random() < .10:
            delay = local_rng.uniform(95 * 60, 130 * 60)
        # Cap before conversion so a huge finite factor cannot overflow timestamps.
        delay = round(min(OUTCOME_RULES.censor_s, delay * scales.get(block.block_id, 1.0)))
        if scenario < .05:
            continue
        start = block.planned_start_ms
        end = start + _WINDOW_S * 1000
        work_start = start + delay * 1000
        has_work = delay < OUTCOME_RULES.censor_s
        prefix_end = work_start if has_work else end
        cursor = start
        first_distraction = local_rng.random() < (.8 if morning else .5)
        count = local_rng.randint(2, 5)
        for index in range(count):
            stop = start + (prefix_end - start) * (index + 1) // count
            if stop <= cursor:
                continue
            if index == 0 and not first_distraction:
                # Use a neutral window unless this block's broad matcher calls it work.
                neutral = _span(cursor, stop, "explorer.exe")
                if categorize(neutral, block, Settings()) == Category.work:
                    neutral = _span(cursor, stop, "__paused__", idle=True)
                result.append(neutral)
            else:
                result.append(_span(cursor, stop, *distractions[index % len(distractions)]))
            cursor = stop
        if has_work:
            work_end = min(end, work_start + max(16 * 60,
                                                min(block.planned_minutes, 60) * 60) * 1000)
            result.append(_span(work_start, work_end, *work))
            if work_end < end:
                # Empty locked title: no synthetic sensitive screen contents either.
                result.append(_span(work_end, end, "LockApp.exe", idle=True, locked=True))
    # Fill only the complement of reserved windows. Device-off windows stay empty,
    # including the margin the real evaluator needs after the censor deadline.
    background_rng = Random(rng.getrandbits(128))
    awake_start = int(datetime.combine(day, time(8)).timestamp() * 1000)
    awake_end = int(datetime.combine(day, time(22)).timestamp() * 1000)
    cursor = day_start
    for begin, end in [(b.planned_start_ms, b.planned_start_ms + _WINDOW_S * 1000)
                       for b in ordered] + [(day_end, day_end)]:
        a, b = max(cursor, awake_start), min(begin, awake_end)
        if a < b:
            middle = a + (b - a) * 2 // 3
            if middle > a:
                result.append(_span(a, middle, "explorer.exe"))
            paused = background_rng.random() < .35
            result.append(_span(middle, b, "__paused__" if paused else "LockApp.exe",
                                idle=True, locked=not paused))
        cursor = end
    return sorted(result, key=lambda s: s.start_ms)
