"""Read-only measurement checks before the first real experiment (Frente A).

Close the app before running. This does not start, stop or withdraw an experiment,
evaluate treatment effects, reveal seeds, or certify data provenance or power.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.contracts import JOURNAL_PAYLOADS, OUTCOME_RULES, Arm, Settings
from core.journal import Journal


MEASUREMENT_SETTINGS = frozenset({"distraction_processes", "distraction_title_patterns",
                                  "browser_processes", "whitelist_processes"})
BASELINE_DAYS = 7  # The project's baseline week, not a statistical power criterion.


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        info = path.stat()
        return info.st_size, info.st_mtime_ns
    except FileNotFoundError:
        return None


def _activity(path: Path) -> dict:
    # Immutable mode never creates a WAL/SHM or writes the database. Refuse WALs
    # instead of silently ignoring uncheckpointed observations. Check again later.
    if path.with_name(path.name + "-wal").exists():
        raise ValueError("activity database needs an offline checkpoint")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("activity database integrity check failed")
        count = observed = paused = 0
        first = previous_end = None
        # Deliberately never SELECT titles or process names. Only a boolean pause flag.
        for start, end, is_paused in db.execute(
                "SELECT start_ms,end_ms,process='__paused__' FROM spans ORDER BY start_ms"):
            if end <= start or (previous_end is not None and start < previous_end):
                raise ValueError("invalid or overlapping activity")
            first = start if first is None else first
            previous_end = end
            count += 1
            observed += end - start
            paused += (end - start) if is_paused else 0
    return {"span_count": count, "observed_s": observed / 1000,
            "paused_s": paused / 1000, "first_ms": first, "last_ms": previous_end}


def _journal(path: Path, problems: set[str]) -> dict:
    journal = Journal(path)  # Parent and file already exist. No append or tail repair.
    verified = journal.verify()
    if journal.torn_tail is not None:
        problems.add("journal_torn_tail")
    confirmed, assignments, outcomes = {}, {}, {}
    active, registered = set(), set()
    baseline_dates, baseline_blocks = set(), 0
    statuses = Counter()
    for event in journal.events():
        kind = event["kind"]
        if kind not in JOURNAL_PAYLOADS:
            problems.add("unknown_journal_event")
            continue
        model = JOURNAL_PAYLOADS[kind]
        item = model.model_validate(event["payload"]) if model else event["payload"]
        if kind == "block_confirmed":
            date.fromisoformat(item.local_date)
            if item.block_id in confirmed:
                problems.add("duplicate_block")
            confirmed[item.block_id] = item
        elif kind == "assignment":
            if item.block_id in assignments:
                problems.add("duplicate_assignment")
            if item.block_id not in confirmed:
                problems.add("assignment_without_block")
            if item.experiment_id is None:
                if item.arm != Arm.control or item.draw_index is not None:
                    problems.add("invalid_baseline_assignment")
            elif item.experiment_id not in active:
                problems.add("assignment_without_active_preregistration")
            assignments[item.block_id] = item
        elif kind == "preregistration":
            if item.experiment_id in registered or active:
                problems.add("overlapping_or_duplicate_experiments")
            if item.outcome_rules != OUTCOME_RULES:
                problems.add("preregistered_measurement_rules_differ")
            active.add(item.experiment_id)
            registered.add(item.experiment_id)
        elif kind == "resolution":
            if item.experiment_id not in active:
                problems.add("resolution_without_active_preregistration")
            active.discard(item.experiment_id)
        elif kind == "settings_changed" and active:
            if MEASUREMENT_SETTINGS.intersection(item.get("keys", [])):
                problems.add("measurement_settings_changed_during_experiment")
        elif kind == "outcome":
            if item.block_id in outcomes:
                problems.add("duplicate_outcome")
                continue
            outcomes[item.block_id] = item
            statuses[item.status] += 1
            block = confirmed.get(item.block_id)
            assignment = assignments.get(item.block_id)
            if block is None or assignment is None:
                problems.add("outcome_without_block_or_assignment")
                continue
            if item.status == "pending":
                problems.add("pending_outcome_in_journal")
                continue
            if item.censored != (item.status == "censored"):
                problems.add("inconsistent_outcome")
            if item.status == "started":
                if (item.latency_s is None or not 0 <= item.latency_s < OUTCOME_RULES.censor_s
                        or item.work_run_start_ms is None
                        or abs(item.work_run_start_ms - block.planned_start_ms - item.latency_s * 1000) > 1
                        or item.computed_ms < item.work_run_start_ms + OUTCOME_RULES.work_run_s * 1000):
                    problems.add("inconsistent_outcome")
            elif item.latency_s is not None or item.work_run_start_ms is not None:
                problems.add("inconsistent_outcome")
            elif item.computed_ms < block.planned_start_ms + OUTCOME_RULES.censor_s * 1000:
                problems.add("premature_final_outcome")
            if item.status != "device_off" and item.features is None:
                problems.add("missing_outcome_features")
            # Baseline means observations completed before the FIRST preregistration,
            # not later control assignments or days containing only device-off.
            if (not registered and assignment.experiment_id is None
                    and assignment.arm == Arm.control and item.status != "device_off"):
                baseline_dates.add(block.local_date)
                baseline_blocks += 1
    # A calendar week can include days without planned work. This is only a
    # temporal check; the council still owns sample-size and power requirements.
    calendar_days = ((date.fromisoformat(max(baseline_dates))
                      - date.fromisoformat(min(baseline_dates))).days + 1) if baseline_dates else 0
    if calendar_days < BASELINE_DAYS:
        problems.add("baseline_week_incomplete")
    return {"verified_events": verified, "outcome_counts": dict(sorted(statuses.items())),
            "baseline_observed_days": len(baseline_dates), "baseline_calendar_days": calendar_days,
            "baseline_blocks": baseline_blocks,
            "active_experiments": len(active)}


def check_data_dir(data_dir: Path) -> dict:
    """Aggregate checks only. An absent DATA_LABEL follows Health's 'real' default."""
    data_dir = Path(data_dir)
    names = ["DATA_LABEL", "settings.json", "journal.jsonl", "activity.sqlite", "activity.sqlite-wal"]
    before = {name: _stamp(data_dir / name) for name in names}
    problems: set[str] = set()
    warnings = []
    result = {"check": "phase4_measurement_preflight", "rules_version": OUTCOME_RULES.rules_version,
              "baseline_days_required": BASELINE_DAYS, "data_label": "real",
              "journal": None, "activity": None}
    marker = data_dir / "DATA_LABEL"
    try:
        if marker.exists():
            label = marker.read_text(encoding="utf-8-sig").strip()
            if label not in {"real", "sintetico"}:
                problems.add("invalid_data_label")
                result["data_label"] = "unknown"
            else:
                result["data_label"] = label
            if label == "sintetico":
                problems.add("synthetic_dataset")
        else:
            warnings.append("unmarked_data_provenance_not_verified")
        settings = data_dir / "settings.json"
        if settings.exists():
            Settings.model_validate_json(settings.read_text(encoding="utf-8-sig"))
        else:
            warnings.append("settings_file_missing_defaults_apply")
    except Exception:
        problems.add("invalid_label_or_settings")
    journal = data_dir / "journal.jsonl"
    if not journal.is_file():
        problems.update({"missing_journal", "baseline_week_incomplete"})
    else:
        try:
            result["journal"] = _journal(journal, problems)
        except Exception:
            problems.add("journal_invalid_or_unreadable")
    activity = data_dir / "activity.sqlite"
    if not activity.is_file():
        problems.add("missing_activity")
    else:
        try:
            result["activity"] = _activity(activity)
            if not result["activity"]["span_count"]:
                problems.add("empty_activity")
        except Exception:
            problems.add("activity_invalid_unreadable_or_has_wal")
    if before != {name: _stamp(data_dir / name) for name in names}:
        problems.add("data_changed_during_check")
    result.update(measurement_checks_passed=not problems, problems=sorted(problems), warnings=warnings)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = check_data_dir(args.data_dir)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["measurement_checks_passed"] else 1
    except Exception as exc:
        print(f"Preflight could not complete ({type(exc).__name__}); no source contents printed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
