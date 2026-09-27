import json

import pytest

from core.contracts import BlockOutcome
from tools.capture.replay import main, replay_trace
from tools.capture.sanitize import sanitize_file
from tools.capture.trace import load_trace

from .conftest import P, ROOT, synthetic_span as span


def save_trace(path, spans):
    path.write_text("".join(item.model_dump_json() + "\n" for item in spans), encoding="utf-8")


def test_replay_defaults_to_observation_end_without_forcing_censor(tmp_path, block, settings):
    source = tmp_path / "short.synthetic.jsonl"
    save_trace(source, [span(0, 10)])
    result = replay_trace(source, block, settings)
    assert result.status == "pending" and result.computed_ms == P + 10000
    assert replay_trace(source, block, settings, P + 5400000).status == "censored"


def test_replay_sanitized_fixture_has_reviewed_result(block, settings):
    result = replay_trace(ROOT / "tests/fixtures/traces/start.synthetic.jsonl", block, settings)
    assert result.status == "started" and result.latency_s == 300
    assert result.features.distraction_s_before_start == 300
    assert result.features.pre_start_switches == 0


def test_real_windows_idle_capture_matches_reviewed_pending_outcome(block, settings):
    traces = ROOT / "tests/fixtures/traces"
    source = traces / "phase2-windows-20260927.jsonl"
    rows = load_trace(source)
    # Only the observation is real; the reference block is explicitly a test scenario.
    reference = block.model_copy(update={"planned_start_ms": rows[0].start_ms})
    expected = BlockOutcome.model_validate_json(
        (traces / "phase2-windows-20260927.outcome.json").read_text(encoding="utf-8"))
    assert replay_trace(source, reference, settings) == expected
    assert all(row.title == "" for row in rows)


@pytest.mark.parametrize("rows", [[span(2, 1)], [span(0, 10), span(9, 20)],
                                  [span(10, 20), span(0, 10)]])
def test_bad_trace_neither_replays_nor_exports_a_partial_fixture(tmp_path, rows, settings):
    raw, clean = tmp_path / "bad.raw.jsonl", tmp_path / "clean.jsonl"
    save_trace(raw, rows)
    with pytest.raises(ValueError, match="invalid or overlapping"):
        load_trace(raw)
    with pytest.raises(ValueError):
        sanitize_file(raw, clean, [], settings)
    assert not clean.exists()


def test_replay_cli_prints_only_derived_outcome_and_checks_expected_fixture(tmp_path, block, capsys):
    source, local_block, output = (tmp_path / name for name in
                                    ("recording.synthetic.jsonl", "block.json", "outcome.json"))
    save_trace(source, [span(0, 900, title="PRIVATE_CAPTION")])
    block.task_label = "PRIVATE_TASK_LABEL"
    local_block.write_text(block.model_dump_json(), encoding="utf-8")
    argv = [str(source), "--block", str(local_block)]
    assert main([*argv, "--output", str(output)]) == 0
    captured = capsys.readouterr()
    assert "PRIVATE_" not in captured.out + captured.err
    assert BlockOutcome.model_validate_json(captured.out).status == "started"
    assert main([*argv, "--expect", str(output)]) == 0
    wrong = json.loads(output.read_text())
    wrong["latency_s"] = 99
    output.write_text(json.dumps(wrong))
    assert main([*argv, "--expect", str(output)]) == 1
    assert main([*argv, "--output", str(output)]) == 1


def test_replay_cli_does_not_echo_invalid_local_block(tmp_path, capsys):
    block_path = tmp_path / "bad-block.json"
    block_path.write_text('{"task_label": "PRIVATE_TASK_LABEL"}')
    assert main([str(tmp_path / "missing.jsonl"), "--block", str(block_path)]) == 1
    captured = capsys.readouterr()
    assert "PRIVATE_TASK_LABEL" not in captured.err + captured.out
