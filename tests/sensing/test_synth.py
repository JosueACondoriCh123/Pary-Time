"""Synthetic scenarios exercise the real classifier and outcome@1 evaluator."""
from datetime import date, datetime, time
from functools import partial
from random import Random
from statistics import median

import pytest

from core.contracts import Settings
from core.sensing.outcome import evaluate_block
from tools.capture.synth import synth_day as generate

synth_day = partial(generate, profile="tdah_mananas")


DAY = date(2026, 9, 27)


def at_hour(block, hour, index=0):
    start = int(datetime.combine(DAY, time(hour)).timestamp() * 1000)
    return block.model_copy(update={"local_date": DAY.isoformat(), "planned_start_ms": start,
                                    "block_id": f"blk_{index:012x}"})


def outcome(block, spans):
    return evaluate_block(block, spans, block.planned_start_ms + 6360_000, Settings())


def test_reproducible_ordered_and_input_order_independent(block):
    blocks = [at_hour(block, 9), at_hour(block, 15, 1)]
    first = generate(DAY, blocks, "tdah_mananas", Random(7))
    assert first == generate(DAY, list(reversed(blocks)), "tdah_mananas", Random(7))
    assert first != synth_day(DAY, blocks, rng=Random(8))
    assert all(s.start_ms < s.end_ms for s in first)
    assert all(a.end_ms <= b.start_ms for a, b in zip(first, first[1:]))
    assert all(not s.title for s in first if s.process == "__paused__" or s.locked)


def test_mornings_slower_with_distraction_and_all_scenarios_observed(block):
    morning, afternoon = at_hour(block, 9), at_hour(block, 15, 1)
    latencies = [[], []]
    statuses = set()
    paused = False
    first_distractions = 0
    morning_started = 0
    for seed in range(100):
        spans = synth_day(DAY, [morning, afternoon], rng=Random(seed))
        paused |= any(s.process == "__paused__" for s in spans)
        for i, item in enumerate([morning, afternoon]):
            result = outcome(item, spans)
            statuses.add(result.status)
            if result.status == "started":
                latencies[i].append(result.latency_s)
                if i == 0:
                    morning_started += 1
                    first_distractions += result.features.first_category == "distraction"
    assert median(latencies[0]) > 2 * median(latencies[1])
    assert 15 * 60 < median(latencies[0]) < 35 * 60
    assert 4 * 60 < median(latencies[1]) < 12 * 60
    assert .65 < first_distractions / morning_started < .95
    assert statuses == {"started", "censored", "device_off"}
    assert paused


def test_scaling_changes_real_latency_without_changing_later_random_draws(block):
    first, second = at_hour(block, 9), at_hour(block, 15, 1)
    baseline = synth_day(DAY, [first, second], rng=Random(7))
    treated = synth_day(DAY, [first, second], rng=Random(7),
                        latency_scale={first.block_id: .5})
    before, after = outcome(first, baseline), outcome(first, treated)
    assert before.status == after.status == "started"
    assert abs(after.latency_s - before.latency_s * .5) <= .5
    assert [s for s in baseline if s.start_ms >= second.planned_start_ms] == [
        s for s in treated if s.start_ms >= second.planned_start_ms]
    immediate = synth_day(DAY, [first], rng=Random(7), latency_scale={first.block_id: 0})
    assert outcome(first, immediate).latency_s == 0
    assert outcome(first, immediate).features.started_early
    delayed = synth_day(DAY, [first], rng=Random(7), latency_scale={first.block_id: 100})
    assert outcome(first, delayed).status == "censored"


def test_private_block_fields_never_copied_and_private_matchers_rejected(block):
    item = at_hour(block, 9).model_copy(update={"task_label": "private canary",
                                             "first_step": "private canary"})
    assert "private canary" not in str(synth_day(DAY, [item], rng=Random(7)))
    item = item.model_copy(update={"work_matchers": [
        block.work_matchers[0].model_copy(update={"field": "title", "pattern": "private/canary"})]})
    with pytest.raises(ValueError, match="generic synthetic") as error:
        synth_day(DAY, [item], rng=Random(7))
    assert "private/canary" not in str(error.value)


@pytest.mark.parametrize("factor", [-1, float("nan"), float("inf"), True, "0.5"])
def test_bad_scale_does_not_advance_rng(block, factor):
    item = at_hour(block, 9)
    rng = Random(7)
    state = rng.getstate()
    with pytest.raises(ValueError):
        synth_day(DAY, [item], rng=rng, latency_scale={item.block_id: factor})
    assert rng.getstate() == state


def test_rejects_ambiguous_windows_and_profile(block):
    item = at_hour(block, 9)
    for blocks in ([item, item], [item, at_hour(block, 10, 1)], [at_hour(block, 23)],
                   [item.model_copy(update={"local_date": "2026-09-28"})]):
        with pytest.raises(ValueError):
            synth_day(DAY, blocks, rng=Random(7))
    with pytest.raises(ValueError):
        generate(DAY, [item], "unknown", Random(7))
    with pytest.raises(ValueError):
        synth_day(DAY, [item], rng=None)
    with pytest.raises(ValueError):
        synth_day(DAY, [item], rng=Random(7), latency_scale={"unknown": 1})
    assert synth_day(DAY, [], rng=Random(7))


def test_process_and_title_matchers_produce_work_and_16_minutes(block):
    from core.sensing.categorize import categorize

    for field, pattern in [("process", "DemoEditor.exe"), ("title", "demo-document")]:
        item = at_hour(block, 9).model_copy(update={"work_matchers": [
            block.work_matchers[0].model_copy(update={"field": field, "pattern": pattern})]})
        spans = synth_day(DAY, [item], rng=Random(7))
        work = [s for s in spans if categorize(s, item, Settings()) == "work"]
        assert len(work) == 1
        assert work[0].end_ms - work[0].start_ms >= 16 * 60_000
        assert pattern in getattr(work[0], field)


def test_scale_halves_distribution_and_preserves_off_blocks(block):
    item = at_hour(block, 9)
    before, after = [], []
    for seed in range(100):
        base = outcome(item, synth_day(DAY, [item], rng=Random(seed)))
        scaled = outcome(item, synth_day(DAY, [item], rng=Random(seed),
                                         latency_scale={item.block_id: .5}))
        assert (base.status == "device_off") == (scaled.status == "device_off")
        if base.status == "started":
            before.append(base.latency_s)
            after.append(scaled.latency_s)
    assert abs(median(after) - median(before) * .5) <= .5
