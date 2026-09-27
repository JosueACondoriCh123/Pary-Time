"""Invented evidence only: real journal hashing, contracts, SQLite and evaluator.

The fixture's 'real' marker tests the label gate; it is NOT a real experiment.
"""
from datetime import datetime
import json

import pytest

from core.contracts import (Arm, Assignment, BlockConfirmed, Resolution,
                            permuted_arm, seed_commitment)
from core.journal import Journal, append_typed
from tools.capture.release_check import check_release, check_resolutions, check_soak, main
from .test_preflight import dataset, files_digest, prereg  # Real SQLite/journal fixture owned by A.


@pytest.fixture
def completed(dataset, block, tmp_path):
    root, journal = dataset
    revealed = "23" * 32  # Public synthetic commitment input, never a user's seed.
    start = int(datetime(2026, 9, 22, 9).timestamp() * 1000)
    registration = prereg(journal, seed_commitment=seed_commitment(revealed), n_per_arm=4,
                         created_ms=start - 60000)
    # Reuse an evaluated baseline outcome; only its declared block/time changes.
    baseline_outcome = next(e["payload"] for e in journal.events() if e["kind"] == "outcome")
    for index in range(8):
        bid = f"blk_{index + 100:012x}"
        planned = start + index * 7200000
        arm = permuted_arm(revealed, registration.experiment_id, index, registration.arms[1])
        append_typed(journal, "block_confirmed", BlockConfirmed(
            block_id=bid, local_date=datetime.fromtimestamp(planned / 1000).date().isoformat(),
            planned_start_ms=planned, planned_minutes=30, task_kind=block.task_kind))
        append_typed(journal, "assignment", Assignment(block_id=bid, experiment_id=registration.experiment_id,
                     arm=arm, draw_index=index, assigned_ms=planned - 1000))
        append_typed(journal, "outcome", dict(baseline_outcome, block_id=bid,
                     computed_ms=planned + 1560000, work_run_start_ms=planned + 600000))
    resolution = Resolution(experiment_id=registration.experiment_id, resolved_ms=planned + 1560001,
                            verdict="not_supported", n_control=4, n_treatment=4,
                            median_control_s=600, median_treatment_s=600, ratio=1, p_value=1,
                            alpha=registration.alpha, censored_control=0, censored_treatment=0,
                            excluded_device_off=0, aborted_blocks=0, seed_revealed=revealed)
    soak = root / "synthetic-soak-evidence.json"
    soak.write_text(json.dumps(dict(schema_version=1, data_label="sintetico", native_capture=False,
        mode="realtime", status="completed", checks_passed=True, wall_48h_completed=True,
        integrity_ok=True, issues=[], requested_seconds=172800, logical_seconds=172800,
        elapsed_wall_s=172800.1, samples=172320, intentional_gap_ticks=480, scheduler_missed_ticks=0,
        max_scheduler_gap_s=0, invalid_spans=0, overlaps=0, expired_spans=0, unexpected_states=0)))
    return root, journal, resolution, soak


def test_recorded_resolution_and_soak_are_read_only_and_do_not_publish_values(completed, capsys):
    root, journal, resolution, soak = completed
    append_typed(journal, "resolution", resolution)
    before = files_digest(root)
    assert main(["--data-dir", str(root), "--soak-status", str(soak)]) == 0
    raw = capsys.readouterr().out
    report = json.loads(raw)
    assert report["a_checks_passed"]
    assert report["resolution"]["recorded_resolutions"] == 1
    assert report["resolution"]["verified_assignments"] == 8
    assert all(value not in raw for value in (resolution.seed_revealed, resolution.experiment_id,
               "p_value", "median_control_s", "private synthetic canary", str(root), "WINWORD"))
    assert files_digest(root) == before


@pytest.mark.parametrize("change,problem", [
    ({"seed_revealed": "45" * 32}, "resolution_commitment_mismatch"),
    ({"n_control": 3}, "resolution_counts_mismatch"),
    ({"censored_treatment": 1}, "resolution_counts_mismatch"),
    ({"excluded_device_off": 1}, "resolution_counts_mismatch"),
    ({"aborted_blocks": 1}, "resolution_counts_mismatch"),
    ({"alpha": 0.04}, "resolution_preregistration_mismatch"),
    ({"resolved_ms": 1}, "resolution_precedes_outcome"),
])
def test_inconsistent_resolution_fails(completed, change, problem):
    root, journal, resolution, soak = completed
    append_typed(journal, "resolution", resolution.model_copy(update=change))
    report = check_release(root, soak)
    assert not report["a_checks_passed"]
    assert problem in report["resolution"]["problems"]


def test_duplicate_and_missing_resolutions_fail(completed):
    root, journal, resolution, soak = completed
    assert "no_recorded_resolution" in check_release(root, soak)["resolution"]["problems"]
    append_typed(journal, "resolution", resolution)
    append_typed(journal, "resolution", resolution)
    assert not check_release(root, soak)["a_checks_passed"]


@pytest.mark.parametrize("marker", [None, "sintetico"])
def test_unmarked_or_demo_data_never_meets_real_data_gate(completed, marker):
    root, journal, resolution, soak = completed
    append_typed(journal, "resolution", resolution)
    if marker is None:
        (root / "DATA_LABEL").unlink()
    else:
        (root / "DATA_LABEL").write_text(marker)
    assert "explicit_real_label_required" in check_release(root, soak)["problems"]


@pytest.mark.parametrize("change", [
    {"mode": "accelerated"}, {"status": "running"}, {"status": "failed"},
    {"elapsed_wall_s": 172799.9}, {"elapsed_wall_s": float("nan")},
    {"wall_48h_completed": False}, {"checks_passed": "true"}, {"overlaps": 1},
    {"issues": ["heap_growth"]}, {"samples": True}, {"samples": 172319},
    {"max_scheduler_gap_s": 10}, {"schema_version": True},
])
def test_accelerated_pending_short_or_inconsistent_soak_never_passes(completed, change):
    _, _, _, soak = completed
    report = json.loads(soak.read_text())
    soak.write_text(json.dumps(dict(report, **change)))
    assert not check_soak(soak)["checks_passed"]


def test_corrupt_journal_and_soak_do_not_leak_payloads(completed):
    root, journal, _, soak = completed
    journal.path.write_text("private-payload-canary\n")
    soak.write_text("private-soak-canary")
    raw = json.dumps(check_release(root, soak))
    assert "private-payload-canary" not in raw
    assert "private-soak-canary" not in raw
    assert not json.loads(raw)["a_checks_passed"]


def test_missing_sources_are_not_created(tmp_path):
    root = tmp_path / "missing"
    assert not check_release(root, root / "status.json")["a_checks_passed"]
    with pytest.raises(ValueError):
        check_resolutions(root / "journal.jsonl")
    assert not root.exists()


@pytest.mark.parametrize("mode,problem", [("arm", "resolution_assignment_mismatch"),
    ("index", "resolution_draw_sequence_invalid"), ("arms", "resolution_arms_invalid")])
def test_valid_hash_chain_does_not_hide_invalid_randomization(completed, mode, problem):
    root, journal, resolution, soak = completed
    append_typed(journal, "resolution", resolution)
    events = list(journal.events())
    journal.path.unlink()
    rewritten = Journal(journal.path)
    for event in events:
        payload = dict(event["payload"])
        if event["kind"] == "assignment" and payload.get("draw_index") == 7:
            if mode == "arm":
                payload["arm"] = "control" if payload["arm"] != "control" else "retrasar_distracciones"
            if mode == "index":
                payload["draw_index"] = 8
        if event["kind"] == "preregistration" and mode == "arms":
            payload["arms"] = ["control", "control"]
        append_typed(rewritten, event["kind"], payload)
    assert rewritten.verify() == len(events)
    assert problem in check_release(root, soak)["resolution"]["problems"]
