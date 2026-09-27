import json
from pathlib import Path

from core.contracts import OUTCOME_RULES, BlockOutcome
from core.stats.analysis import analyze

EX = Path(__file__).resolve().parents[2] / "contracts" / "examples"


def outcome(i, latency=None, status="started"):
    base = json.loads((EX / "BlockOutcome.started.json").read_text(encoding="utf-8"))
    base.update(block_id=f"blk_{i:012x}", status=status, latency_s=latency if status == "started" else None,
                censored=status == "censored", work_run_start_ms=None)
    return BlockOutcome.model_validate(base)


def test_itt_analysis_counts_censored_as_90_min_and_excludes_device_off():
    control = [outcome(i, lat) for i, lat in enumerate([1500, 1800, 2400, 900, 1300])] + \
              [outcome(10, status="censored"), outcome(11, status="device_off")]
    treat = [outcome(20 + i, lat) for i, lat in enumerate([300, 420, 250, 600, 380, 500])]
    a = analyze(control, treat, n_per_arm=6, alpha=0.05, experiment_id="exp_0123456789ab", rules=OUTCOME_RULES)
    assert (a.n_control, a.n_treatment, a.censored_control, a.excluded_device_off) == (6, 6, 1, 1)
    assert a.median_control_s == 1650.0 and a.median_treatment_s == 400.0
    assert a.verdict == "supported" and a.p_value <= 0.05 and a.ratio == round(400 / 1650, 4)


def test_short_arm_is_insufficient_and_reports_no_effect():
    a = analyze([outcome(1, 100)], [outcome(2, 50)], n_per_arm=4, alpha=0.05, experiment_id="exp_x",
                rules=OUTCOME_RULES)
    assert a.verdict == "insufficient" and a.p_value is None and a.median_control_s is None


def test_same_inputs_same_p_value():
    c = [outcome(i, 1000 + 37 * i) for i in range(14)]
    t = [outcome(50 + i, 800 + 41 * i) for i in range(14)]
    kw = dict(n_per_arm=14, alpha=0.025, experiment_id="exp_abcdefabcdef", rules=OUTCOME_RULES)
    assert analyze(c, t, **kw) == analyze(c, t, **kw)
