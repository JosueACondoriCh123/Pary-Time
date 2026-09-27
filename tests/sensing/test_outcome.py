import pytest

from core.contracts import ActivitySpan, Category
from core.sensing.outcome import evaluate_block

from .conftest import P, ROOT, synthetic_span as span


def evaluate(block, settings, spans, now=6300):
    return evaluate_block(block, spans, P + round(now * 1000), settings)


def test_normal_start_uses_run_beginning_not_completion(block, settings):
    result = evaluate(block, settings, [span(0, 100, "chrome.exe", "youtube"), span(100, 1000)])
    assert result.status == "started" and result.latency_s == 100
    assert result.work_run_start_ms == P + 100000 and not result.censored
    assert result.rules_version == "outcome@1"


@pytest.mark.parametrize("gap,latency", [(59, 10), (60, 670), (61, 671)])
@pytest.mark.parametrize("filled", [False, True])
def test_gap_threshold_is_strict(block, settings, gap, latency, filled):
    spans = [span(10, 610), span(610 + gap, 1510 + gap)]
    if filled:
        spans.insert(1, span(610, 610 + gap, "explorer.exe", ""))
    assert evaluate(block, settings, spans).latency_s == latency


@pytest.mark.parametrize("state", ["idle", "locked"])
def test_idle_and_locked_work_app_do_not_count(block, settings, state):
    spans = [span(0, 120), span(120, 1000, **{state: True}), span(1000, 1900)]
    assert evaluate(block, settings, spans).latency_s == 1000


def test_early_work_is_clipped_and_must_still_last_fifteen_minutes(block, settings):
    spans = [span(-2000, 900)]
    pending = evaluate(block, settings, spans, 899)
    result = evaluate(block, settings, spans, 900)
    assert pending.status == "pending"
    assert result.latency_s == 0 and result.features.started_early
    assert result.features.sensor_coverage == 1
    assert result.features.first_category == Category.work
    assert result.features.pre_start_switches == 0


def test_brief_early_attempt_does_not_label_later_start_early(block, settings):
    result = evaluate(block, settings, [span(-10, 10), span(100, 1000)])
    assert result.latency_s == 100 and not result.features.started_early


def test_censor_requires_deadline_and_has_no_observed_latency(block, settings):
    spans = [span(0, 7000, "Discord.exe", "")]
    assert evaluate(block, settings, spans, 5399).status == "pending"
    result = evaluate(block, settings, spans, 5400)
    assert result.status == "censored" and result.censored
    assert result.latency_s is None and result.work_run_start_ms is None


def test_open_run_at_deadline_can_complete_later(block, settings):
    spans = [span(0, 5350, "explorer.exe", ""), span(5350, 6250)]
    assert evaluate(block, settings, spans, 5400).status == "pending"
    assert evaluate(block, settings, spans, 6249).status == "pending"
    result = evaluate(block, settings, spans, 6250)
    assert result.status == "started" and result.latency_s == 5350


def test_open_run_expires_at_exactly_sixty_seconds(block, settings):
    spans = [span(5390, 5400)]
    assert evaluate(block, settings, spans, 5459.999).status == "pending"
    assert evaluate(block, settings, spans, 5460).status == "censored"


def test_run_beginning_at_deadline_cannot_qualify(block, settings):
    spans = [span(0, 5400, "explorer.exe", ""), span(5400, 8000)]
    assert evaluate(block, settings, spans, 6300).status == "censored"


@pytest.mark.parametrize("spans", [[], [span(-1000, 0)], [span(5400, 7000)]])
def test_device_off_only_when_no_sensor_coverage_before_deadline(block, settings, spans):
    assert evaluate(block, settings, spans, 5399).status == "pending"
    result = evaluate(block, settings, spans, 5400)
    assert result.status == "device_off" and not result.censored
    assert result.features.sensor_coverage == 0


def test_power_on_late_counts_as_latency(block, settings):
    result = evaluate(block, settings, [span(3600, 4500)], 4500)
    assert result.latency_s == 3600 and result.status == "started"
    assert result.features.sensor_coverage == 0


def test_pause_is_observed_nonwork_even_with_matching_matcher(block, settings):
    block.work_matchers[0].pattern = "__paused__"
    result = evaluate(block, settings, [span(0, 5400, "__paused__", "", idle=True)], 5400)
    assert result.status == "censored" and result.features.sensor_coverage == 1
    assert result.features.first_category == Category.other


def test_features_follow_normative_pre_start_interval(block, settings, example_spans):
    result = evaluate(block, settings, example_spans, 1320)
    assert result.latency_s == 420
    assert result.features.model_dump() == dict(pre_start_switches=2, first_category=Category.distraction,
        distraction_s_before_start=270, sensor_coverage=1, started_early=False)


def test_partial_coverage_switches_and_fractional_seconds(block, settings):
    spans = [span(0, 10.9, "Discord.exe", ""), span(20, 30, "explorer.exe", ""), span(40, 940)]
    result = evaluate(block, settings, spans, 940)
    assert result.features.pre_start_switches == 1
    assert result.features.distraction_s_before_start == 10
    assert result.features.sensor_coverage == pytest.approx(20.9 / 40)


def test_future_data_cannot_finalize_and_input_is_not_mutated(block, settings):
    spans = [span(-5, 900)]
    before = spans[0].model_dump()
    assert evaluate(block, settings, spans, -1).status == "pending"
    assert evaluate(block, settings, spans, 899).status == "pending"
    assert spans[0].model_dump() == before


def test_synthetic_jsonl_regression(block, settings):
    spans = [ActivitySpan.model_validate_json(line) for line in
             (ROOT / "tests/fixtures/traces/start.synthetic.jsonl").read_text().splitlines()]
    result = evaluate(block, settings, spans, 2000)
    assert result.latency_s == 300
    assert result.features.distraction_s_before_start == 300


def test_overlapping_observations_are_rejected_without_echoing_titles(block, settings):
    with pytest.raises(ValueError, match="must not overlap"):
        evaluate(block, settings, [span(0, 100), span(50, 1000)])
