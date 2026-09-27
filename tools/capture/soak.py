"""Synthetic stability run against the real sampler compressor and SQLite store.

Never starts WindowsReader or the native sampler thread. Accelerated logical time
is explicitly separate from a wall-clock soak. Reports contain aggregates only.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import sqlite3
import sys
import time
import tracemalloc
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.contracts import ActivitySpan, Settings
from core.sensing.sampler import Sample, Sampler
from core.sensing.store import SpanStore

BASE_MS = 1790467200000  # Fixed synthetic epoch, independent of the host clock.
DAY_MS = 86400000
STATES = (
    ("soak-work.exe", "synthetic work", False, False),
    ("soak-browser.exe", "synthetic distraction", False, False),
    ("soak-work.exe", "synthetic idle", True, False),
    ("?", "", True, True),
    ("__paused__", "", True, False),
)


def synthetic_sample(second: int) -> Sample | None:
    # Ten unobserved seconds per hour; +120 s clock jump followed by rollback.
    if second % 3600 >= 3590:
        return None
    offset = 120 if 7200 <= second % 14400 < 10800 else 0
    state = STATES[(second // 30) % len(STATES)]
    return Sample(BASE_MS + (second + offset) * 1000, float(second), *state)


def process_handles() -> int | None:
    """Only count this process's handles; no process enumeration or window reads."""
    if sys.platform != "win32":
        return None
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessHandleCount.restype = wintypes.BOOL
    count = wintypes.DWORD()
    if not kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(count)):
        raise OSError("process handle measurement failed")
    return count.value


def inspect_database(path: Path, cutoff_ms: int | None) -> dict:
    """Read invariants without exporting titles, process names, or SQL row values."""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        integrity_ok = db.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        rows, invalid = db.execute(
            "SELECT count(*), coalesce(sum(end_ms <= start_ms), 0) FROM spans"
        ).fetchone()
        overlaps = db.execute("""SELECT count(*) FROM (
            SELECT start_ms, lag(end_ms) OVER (ORDER BY start_ms) AS previous_end
            FROM spans) WHERE previous_end > start_ms""").fetchone()[0]
        expired = db.execute("SELECT count(*) FROM spans WHERE start_ms < ?",
                             (cutoff_ms if cutoff_ms is not None else 0,)).fetchone()[0]
        unexpected = db.execute("""SELECT count(*) FROM spans WHERE NOT (
            (process='soak-work.exe' AND title='synthetic work' AND idle=0 AND locked=0) OR
            (process='soak-browser.exe' AND title='synthetic distraction' AND idle=0 AND locked=0) OR
            (process='soak-work.exe' AND title='synthetic idle' AND idle=1 AND locked=0) OR
            (process='?' AND title='' AND idle=1 AND locked=1) OR
            (process='__paused__' AND title='' AND idle=1 AND locked=0))""").fetchone()[0]
    return dict(rows=rows, integrity_ok=integrity_ok, invalid_spans=invalid,
                overlaps=overlaps, expired_spans=expired, unexpected_states=unexpected)


def _write_report(output: Path, report: dict) -> None:
    temporary = output / "status.tmp"
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output / "status.json")


def run_soak(output: Path, seconds: int, *, realtime: bool = False) -> dict:
    if not isinstance(seconds, int) or not 2 <= seconds <= 14 * 86400:
        raise ValueError("duration must be an integer from 2 seconds to 14 days")
    # Refuse even empty existing directories, so real application data cannot be reused.
    output.mkdir(parents=True, exist_ok=False)
    (output / "DATA_LABEL").write_text("sintetico\n", encoding="utf-8")
    path = output / "activity.sqlite"
    settings = Settings(raw_retention_days=1)
    store = SpanStore(path)
    sampler = Sampler(store, lambda: settings)
    started = time.monotonic()
    owned_tracing = not tracemalloc.is_tracing()
    if owned_tracing:
        tracemalloc.start()
    report = dict(schema_version=1, data_label="sintetico", mode="realtime" if realtime else "accelerated",
                  pid=os.getpid(), started_at_utc=datetime.now(timezone.utc).isoformat(),
                  requested_seconds=seconds, status="running", native_capture=False,
                  samples=0, intentional_gap_ticks=0, scheduler_missed_ticks=0,
                  max_scheduler_gap_s=0, storage_reopens=0, logical_seconds=0,
                  elapsed_wall_s=0, wall_48h_completed=False, issues=[], checks_passed=False)
    cutoff = None
    baseline = None
    next_checkpoint = 60 if realtime else 3600
    previous = -1

    def checkpoint() -> None:
        nonlocal baseline
        inspection = inspect_database(path, cutoff)
        heap, peak = tracemalloc.get_traced_memory()
        handles = process_handles()
        if baseline is None:
            baseline = (heap, handles)
        sizes = [p.stat().st_size for p in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm"))
                 if p.exists()]
        metrics = dict(logical_seconds=report["logical_seconds"],
                       elapsed_wall_s=round(time.monotonic() - started, 3),
                       heap_bytes=heap, peak_heap_bytes=peak, handles=handles,
                       heap_growth_bytes=heap - baseline[0],
                       handle_growth=handles - baseline[1] if handles is not None else None,
                       sqlite_total_bytes=sum(sizes), **inspection)
        report.update(metrics)
        issues = report["issues"]
        for name in ("invalid_spans", "overlaps", "expired_spans", "unexpected_states"):
            if inspection[name] and name not in issues:
                issues.append(name)
        if not inspection["integrity_ok"] and "sqlite_integrity" not in issues:
            issues.append("sqlite_integrity")
        # Generous regression bounds for this bounded synthetic workload, not a
        # general proof of no leaks. Compare after the first reporting checkpoint.
        if metrics["heap_growth_bytes"] > 16 * 1024 * 1024 and "heap_growth" not in issues:
            issues.append("heap_growth")
        if handles is not None and metrics["handle_growth"] > 64 and "handle_growth" not in issues:
            issues.append("handle_growth")
        with (output / "metrics.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(metrics) + "\n")
        _write_report(output, report)

    try:
        # Exercise startup deletion before writing only the fixed synthetic states.
        store.write(ActivitySpan(start_ms=BASE_MS - 3 * DAY_MS, end_ms=BASE_MS - 2 * DAY_MS,
                                 process="expired.exe", title="synthetic expired", idle=False))
        sampler.maintain(BASE_MS, 0)
        cutoff = store._cutoff
        _write_report(output, report)
        tick = 0
        while True:
            if (output / "stop.request").exists():
                raise KeyboardInterrupt
            if realtime:
                elapsed = time.monotonic() - started
                if elapsed < tick:
                    time.sleep(min(tick - elapsed, 1))
                    continue
                tick = int(elapsed)  # Do not backfill time lost during suspension.
                if tick >= seconds:
                    break
            elif tick >= seconds:
                break
            missed = max(0, tick - previous - 1)
            report["scheduler_missed_ticks"] += missed
            report["max_scheduler_gap_s"] = max(report["max_scheduler_gap_s"], missed)
            # Reopen without flushing the compressor, as after losing in-memory state.
            if previous >= 0 and tick // 21600 != previous // 21600:
                store.close()
                store = SpanStore(path)
                sampler = Sampler(store, lambda: settings)
                report["storage_reopens"] += 1
            sample = synthetic_sample(tick)
            wall_ms = sample.wall_ms if sample else BASE_MS + tick * 1000
            sampler.maintain(wall_ms, float(tick))
            cutoff = max(cutoff or 0, store._cutoff or 0)
            if sample is not None:
                sampler._ingest(sample)
                report["samples"] += 1
            else:
                report["intentional_gap_ticks"] += 1
            report["logical_seconds"] = tick + 1
            if tick + 1 >= next_checkpoint:
                checkpoint()
                next_checkpoint = tick + (60 if realtime else 3600) + 1
            previous = tick
            tick += 1
        # End without extrapolating a span using the real system wall clock.
        if realtime:
            tail_gap = max(0, seconds - previous - 1)
            report["scheduler_missed_ticks"] += tail_gap
            report["max_scheduler_gap_s"] = max(report["max_scheduler_gap_s"], tail_gap)
        if (report["scheduler_missed_ticks"] > seconds * 0.01
                or report["max_scheduler_gap_s"] > 5):
            report["issues"].append("scheduler_gaps")
        report["status"] = "completed"
    except KeyboardInterrupt:
        report["status"] = "interrupted"
    except Exception as exc:
        # Exception messages can include paths or raw input; retain the type only.
        report["status"] = "failed"
        report["issues"].append("runtime_error")
        report["error_type"] = type(exc).__name__
    finally:
        store.close()
        try:
            checkpoint()
        except Exception as exc:
            report["issues"].append("report_inspection_failed")
            report["error_type"] = type(exc).__name__
        report["elapsed_wall_s"] = round(time.monotonic() - started, 3)
        report["wall_48h_completed"] = bool(realtime and time.monotonic() - started >= 172800
                                              and report["status"] == "completed")
        if report["status"] == "completed" and report["issues"]:
            report["status"] = "failed"
        report["checks_passed"] = report["status"] == "completed" and not report["issues"]
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            _write_report(output, report)
        finally:
            if owned_tracing:
                tracemalloc.stop()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new directory, preferably under build/")
    parser.add_argument("--mode", choices=("accelerated", "realtime"), default="accelerated")
    parser.add_argument("--hours", type=float, default=48)
    parser.add_argument("--seconds", type=int, help="short validation run instead of --hours")
    args = parser.parse_args(argv)
    if not math.isfinite(args.hours) or not 0 < args.hours <= 336:
        parser.error("hours must be positive and no more than 336")
    seconds = args.seconds if args.seconds is not None else round(args.hours * 3600)
    try:
        report = run_soak(args.out, seconds, realtime=args.mode == "realtime")
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(report))
    return 0 if report["checks_passed"] else 130 if report["status"] == "interrupted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
