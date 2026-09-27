"""Local, read-only phase 6 checks for A; never creates a resolution or publishes.

An explicit real label is required but cannot prove provenance. These checks do
not recalculate C's statistics or replace the whole application's release checks.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.contracts import (Arm, Assignment, BlockOutcome, Preregistration, Resolution,
                            permuted_arm, seed_commitment)
from core.journal import Journal
from tools.capture.preflight import _stamp, check_data_dir


def check_resolutions(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("resolution journal is missing")
    problems: set[str] = set()
    registered, assignments, outcomes = {}, {}, {}
    resolved, aborted = set(), set()
    verified_draws = 0
    journal = Journal(path)
    journal.verify()
    if journal.torn_tail is not None:
        problems.add("journal_torn_tail")
    for event in journal.events():
        kind, payload = event["kind"], event["payload"]
        if kind == "preregistration":
            item = Preregistration.model_validate(payload)
            registered[item.experiment_id] = item
        elif kind == "assignment":
            item = Assignment.model_validate(payload)
            assignments[item.block_id] = item
        elif kind == "outcome":
            item = BlockOutcome.model_validate(payload)
            outcomes[item.block_id] = item
        elif kind == "block_abort":
            aborted.add(payload["block_id"])
        elif kind == "resolution":
            item = Resolution.model_validate(payload)
            prereg = registered.get(item.experiment_id)
            if prereg is None or item.experiment_id in resolved:
                problems.add("resolution_missing_or_duplicate_preregistration")
                continue
            resolved.add(item.experiment_id)
            if prereg.arms[0] != Arm.control or prereg.arms[1] == Arm.control:
                problems.add("resolution_arms_invalid")
            if seed_commitment(item.seed_revealed) != prereg.seed_commitment:
                problems.add("resolution_commitment_mismatch")
            draws = [a for a in assignments.values() if a.experiment_id == item.experiment_id]
            indices = [a.draw_index for a in draws]
            if None in indices or sorted(indices) != list(range(len(draws))):
                problems.add("resolution_draw_sequence_invalid")
            for draw in draws:
                if (draw.draw_index is None or draw.arm != permuted_arm(
                        item.seed_revealed, item.experiment_id, draw.draw_index, prereg.arms[1])):
                    problems.add("resolution_assignment_mismatch")
                else:
                    verified_draws += 1
            usable, censored = Counter(), Counter()
            device_off = 0
            for draw in draws:
                outcome = outcomes.get(draw.block_id)
                if outcome is None:
                    continue  # Future confirmed blocks need not have finished yet.
                if outcome.computed_ms > item.resolved_ms:
                    problems.add("resolution_precedes_outcome")
                if outcome.status in {"started", "censored"}:
                    usable[draw.arm] += 1
                    censored[draw.arm] += outcome.status == "censored"
                elif outcome.status == "device_off":
                    device_off += 1
            treatment = prereg.arms[1]
            expected = (usable[Arm.control], usable[treatment], censored[Arm.control],
                        censored[treatment], device_off, sum(a.block_id in aborted for a in draws))
            actual = (item.n_control, item.n_treatment, item.censored_control,
                      item.censored_treatment, item.excluded_device_off, item.aborted_blocks)
            if actual != expected:
                problems.add("resolution_counts_mismatch")
            if min(item.n_control, item.n_treatment) < prereg.n_per_arm:
                problems.add("resolution_sample_size_incomplete")
            if item.alpha != prereg.alpha or item.resolved_ms < prereg.created_ms:
                problems.add("resolution_preregistration_mismatch")
    if not resolved:
        problems.add("no_recorded_resolution")
    return dict(recorded_resolutions=len(resolved), verified_assignments=verified_draws,
                checks_passed=not problems, problems=sorted(problems))


def check_soak(path: Path) -> dict:
    """Only a completed realtime report can satisfy the duration requirement."""
    problems = []
    try:
        before = _stamp(path)
        report = json.loads(path.read_text(encoding="utf-8-sig"))
        required_true = ("checks_passed", "wall_48h_completed", "integrity_ok")
        integers = ("requested_seconds", "logical_seconds", "samples", "intentional_gap_ticks",
                    "scheduler_missed_ticks", "max_scheduler_gap_s")
        zero_counts = ("invalid_spans", "overlaps", "expired_spans", "unexpected_states")
        elapsed = report.get("elapsed_wall_s")
        if (type(report.get("schema_version")) is not int or report["schema_version"] != 1
                or report.get("data_label") != "sintetico"
                or report.get("native_capture") is not False
                or report.get("mode") != "realtime" or report.get("status") != "completed"
                or any(report.get(k) is not True for k in required_true)
                or report.get("issues") != []
                or any(type(report.get(k)) is not int or report[k] < 0 for k in integers)
                or any(type(report.get(k)) is not int or report[k] != 0 for k in zero_counts)
                or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 172800):
            problems.append("soak_not_completed_48h_realtime")
        else:
            requested = report["requested_seconds"]
            if (requested < 172800 or not 172800 <= report["logical_seconds"] <= requested
                    or report["samples"] + report["intentional_gap_ticks"]
                    + report["scheduler_missed_ticks"] != requested
                    or report["samples"] < requested * 0.95
                    or report["max_scheduler_gap_s"] > 5
                    or report["scheduler_missed_ticks"] > requested * 0.01):
                problems.append("soak_coverage_invalid")
        if before != _stamp(path):
            problems.append("soak_report_changed_during_check")
    except Exception:
        problems.append("soak_report_missing_or_invalid")
    # Do not reflect arbitrary report fields or exception messages into the output.
    return dict(checks_passed=not problems, problems=problems)


def check_release(data_dir: Path, soak_status: Path) -> dict:
    names = ("DATA_LABEL", "settings.json", "journal.jsonl", "activity.sqlite", "activity.sqlite-wal")
    before = {name: _stamp(data_dir / name) for name in names}
    measurement = check_data_dir(data_dir)
    problems = []
    if not measurement["measurement_checks_passed"]:
        problems.append("measurement_preflight_failed")
    if before["DATA_LABEL"] is None or measurement["data_label"] != "real":
        problems.append("explicit_real_label_required")
    resolution = dict(checks_passed=False, recorded_resolutions=0, verified_assignments=0,
                      problems=["resolution_journal_missing_or_invalid"])
    path = data_dir / "journal.jsonl"
    if path.is_file():
        try:
            resolution = check_resolutions(path)
        except Exception:
            pass
    if not resolution["checks_passed"]:
        problems.append("recorded_resolution_check_failed")
    soak = check_soak(soak_status)
    if not soak["checks_passed"]:
        problems.append("realtime_soak_pending_or_failed")
    if before != {name: _stamp(data_dir / name) for name in names}:
        problems.append("data_changed_during_check")
    return dict(check="phase6_a_local", a_checks_passed=not problems,
                measurement=measurement, resolution=resolution, soak=soak, problems=problems,
                limitations=["data_provenance_not_certified", "statistics_not_recomputed",
                             "soak_report_not_independently_attested", "not_application_release_approval"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--soak-status", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = check_release(args.data_dir, args.soak_status)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["a_checks_passed"] else 1
    except Exception as exc:
        print(json.dumps({"check": "phase6_a_local", "a_checks_passed": False,
                          "error_type": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
