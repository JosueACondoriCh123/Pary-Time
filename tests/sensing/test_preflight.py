"""Entirely SYNTHETIC datasets, with real SQLite, journal hashes and outcome evaluation."""
from datetime import datetime, timedelta
import hashlib
import json
import sqlite3

import pytest

from core.contracts import (ActivitySpan, Arm, Assignment, BlockConfirmed,
                            Preregistration, Settings)
from core.journal import Journal, append_typed
from core.sensing.outcome import evaluate_block
from core.sensing.store import SpanStore
from tools.capture.preflight import check_data_dir, main

from .conftest import ROOT


def files_digest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def dataset(tmp_path, block):
    # 'real' deliberately exercises the real-data gate using invented test data.
    (tmp_path / "DATA_LABEL").write_text("real\n", encoding="utf-8")
    (tmp_path / "settings.json").write_text(Settings().model_dump_json(), encoding="utf-8")
    journal = Journal(tmp_path / "journal.jsonl")
    store = SpanStore(tmp_path / "activity.sqlite")
    for i in range(7):
        day = datetime(2026, 9, 15, 9) + timedelta(days=i)
        start = int(day.timestamp() * 1000)
        item = block.model_copy(update={"block_id": f"blk_{i:012x}",
            "planned_start_ms": start, "local_date": day.date().isoformat()})
        confirmed = BlockConfirmed(**{k: getattr(item, k) for k in (
            "block_id", "planned_start_ms", "planned_minutes", "local_date", "task_kind")})
        append_typed(journal, "block_confirmed", confirmed)
        append_typed(journal, "assignment", Assignment(block_id=item.block_id, arm=Arm.control,
                                                       assigned_ms=start - 60_000))
        spans = [ActivitySpan(start_ms=start, end_ms=start + 600_000, process="chrome.exe",
                             title="youtube", idle=False),
                 ActivitySpan(start_ms=start + 600_000, end_ms=start + 1560_000,
                              process="WINWORD.EXE", title="private synthetic canary", idle=False)]
        for span in spans:
            store.write(span)
        append_typed(journal, "outcome", evaluate_block(item, spans, start + 1560_000, Settings()))
    store.close()
    return tmp_path, journal


def prereg(journal, **updates):
    item = Preregistration.model_validate_json(
        (ROOT / "contracts/examples/Preregistration.json").read_text(encoding="utf-8"))
    item = item.model_copy(update=updates)
    append_typed(journal, "preregistration", item)
    return item


def test_complete_baseline_is_read_only_and_has_no_private_contents(dataset, capsys):
    root, journal = dataset
    before = files_digest(root)
    assert main(["--data-dir", str(root)]) == 0
    raw = capsys.readouterr().out
    result = json.loads(raw)
    assert result["measurement_checks_passed"]
    assert result["journal"]["baseline_observed_days"] == 7
    assert result["journal"]["baseline_blocks"] == 7
    assert result["activity"]["span_count"] == 14
    assert result["activity"]["observed_s"] == 7 * 1560
    assert not any(x in raw for x in [str(root), "private synthetic canary", "WINWORD", "seed"])
    assert files_digest(root) == before


def test_missing_directory_is_not_created(tmp_path):
    root = tmp_path / "absent"
    report = check_data_dir(root)
    assert {"missing_journal", "missing_activity", "baseline_week_incomplete"} <= set(report["problems"])
    assert not root.exists()


@pytest.mark.parametrize("marker,problem", [("sintetico", "synthetic_dataset"), ("typo", "invalid_data_label")])
def test_demo_and_bad_markers_never_pass_as_real(dataset, marker, problem):
    root, _ = dataset
    (root / "DATA_LABEL").write_text(marker, encoding="utf-8")
    assert problem in check_data_dir(root)["problems"]


def test_missing_marker_reports_provenance_limitation(dataset):
    root, _ = dataset
    (root / "DATA_LABEL").unlink()
    result = check_data_dir(root)
    assert result["data_label"] == "real"
    assert "unmarked_data_provenance_not_verified" in result["warnings"]


def test_active_experiment_does_not_reveal_seed_or_effect(dataset):
    root, journal = dataset
    prereg(journal)
    report = check_data_dir(root)
    assert report["measurement_checks_passed"]
    assert report["journal"]["active_experiments"] == 1
    assert all(word not in json.dumps(report) for word in ["seed", "ratio", "p_value", "median"])


def test_measurement_changes_during_experiment_are_flagged(dataset):
    root, journal = dataset
    prereg(journal)
    append_typed(journal, "settings_changed", {"keys": ["raw_retention_days"]})
    assert check_data_dir(root)["measurement_checks_passed"]
    append_typed(journal, "settings_changed", {"keys": ["distraction_title_patterns"]})
    assert "measurement_settings_changed_during_experiment" in check_data_dir(root)["problems"]


def test_preregistered_rules_must_match_frozen_measurement(dataset):
    root, journal = dataset
    example = Preregistration.model_validate_json(
        (ROOT / "contracts/examples/Preregistration.json").read_text(encoding="utf-8"))
    prereg(journal, outcome_rules=example.outcome_rules.model_copy(update={"work_run_s": 60}))
    assert "preregistered_measurement_rules_differ" in check_data_dir(root)["problems"]


def test_duplicate_outcomes_are_rejected(dataset):
    root, journal = dataset
    previous = next(e["payload"] for e in journal.events() if e["kind"] == "outcome")
    append_typed(journal, "outcome", previous)
    assert "duplicate_outcome" in check_data_dir(root)["problems"]


@pytest.mark.parametrize("change,problem", [
    ({"status": "pending"}, "pending_outcome_in_journal"),
    ({"latency_s": -1}, "inconsistent_outcome"),
    ({"status": "censored", "censored": True, "latency_s": None,
      "work_run_start_ms": None}, "premature_final_outcome"),
    ({"features": None}, "missing_outcome_features"),
])
def test_invalid_outcome_semantics_fail_with_valid_journal_hashes(dataset, change, problem):
    root, journal = dataset
    events = list(journal.events())
    (root / "journal.jsonl").unlink()
    replacement = Journal(root / "journal.jsonl")
    for event in events:
        payload = dict(event["payload"])
        if event["kind"] == "outcome":
            payload.update(change)
        append_typed(replacement, event["kind"], payload)
    assert problem in check_data_dir(root)["problems"]


def test_device_off_does_not_supply_a_baseline_day(dataset):
    root, journal = dataset
    events = list(journal.events())
    (root / "journal.jsonl").unlink()
    replacement = Journal(root / "journal.jsonl")
    for event in events:
        payload = dict(event["payload"])
        if event["kind"] == "outcome" and payload["block_id"] == "blk_000000000006":
            payload.update(status="device_off", latency_s=None, work_run_start_ms=None,
                           computed_ms=payload["computed_ms"] + 5400_000)
        append_typed(replacement, event["kind"], payload)
    report = check_data_dir(root)
    assert report["journal"]["baseline_observed_days"] == 6
    assert "baseline_week_incomplete" in report["problems"]


def test_torn_tail_is_reported_without_repair(dataset):
    root, _ = dataset
    path = root / "journal.jsonl"
    with path.open("ab") as stream:
        stream.write(b'{"private synthetic canary":')
    before = files_digest(root)
    assert "journal_torn_tail" in check_data_dir(root)["problems"]
    assert files_digest(root) == before


def test_tampered_journal_fails_without_echoing_source(dataset, capsys):
    root, _ = dataset
    path = root / "journal.jsonl"
    path.write_bytes(path.read_bytes().replace(b'"task_kind":"escritura"', b'"task_kind":"otro"', 1))
    assert main(["--data-dir", str(root)]) == 1
    assert "journal_invalid_or_unreadable" in capsys.readouterr().out


def test_live_wal_is_refused_without_modifying_it(dataset):
    root, _ = dataset
    store = SpanStore(root / "activity.sqlite")
    try:
        store.mark_sample(123)
        before = files_digest(root)
        assert "activity_invalid_unreadable_or_has_wal" in check_data_dir(root)["problems"]
        assert files_digest(root) == before
    finally:
        store.close()


def test_overlapping_stored_spans_are_detected(dataset):
    root, _ = dataset
    with sqlite3.connect(root / "activity.sqlite") as db:
        db.execute("INSERT INTO spans SELECT start_ms+1,end_ms,process,title,idle,locked FROM spans LIMIT 1")
    db.close()
    assert "activity_invalid_unreadable_or_has_wal" in check_data_dir(root)["problems"]


def test_only_distinct_completed_baseline_days_count(dataset):
    root, journal = dataset
    # Rewrite a synthetic TEST dataset with valid hashes and all blocks on one local date.
    events = list(journal.events())
    (root / "journal.jsonl").unlink()
    replacement = Journal(root / "journal.jsonl")
    for e in events:
        payload = dict(e["payload"])
        if e["kind"] == "block_confirmed":
            payload["local_date"] = "2026-09-15"
        append_typed(replacement, e["kind"], payload)
    result = check_data_dir(root)
    assert result["journal"]["baseline_observed_days"] == 1
    assert "baseline_week_incomplete" in result["problems"]


def test_calendar_week_can_include_days_without_planned_work(dataset):
    root, journal = dataset
    events = list(journal.events())
    (root / "journal.jsonl").unlink()
    replacement = Journal(root / "journal.jsonl")
    # Seven blocks across five declared working dates and eight calendar days.
    offsets = [0, 0, 1, 2, 4, 7, 7]
    for event in events:
        payload = dict(event["payload"])
        if event["kind"] == "block_confirmed":
            index = int(payload["block_id"][4:], 16)
            payload["local_date"] = (datetime(2026, 9, 15) + timedelta(days=offsets[index])).date().isoformat()
        append_typed(replacement, event["kind"], payload)
    report = check_data_dir(root)
    assert report["measurement_checks_passed"]
    assert report["journal"]["baseline_observed_days"] == 5
    assert report["journal"]["baseline_calendar_days"] == 8


def test_invalid_settings_never_print_private_validation_values(dataset, capsys):
    root, _ = dataset
    (root / "settings.json").write_text('{"raw_retention_days":"private synthetic canary"}', encoding="utf-8")
    assert main(["--data-dir", str(root)]) == 1
    raw = capsys.readouterr().out
    assert "invalid_label_or_settings" in raw and "private synthetic canary" not in raw
