"""Record local Windows activity, then export raw JSONL for explicit sanitization."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.contracts import Settings
from core.sensing.sampler import Sampler
from core.sensing.store import SpanStore


def export_raw(store: SpanStore, destination: Path, start_ms: int, end_ms: int) -> int:
    spans = store.spans(start_ms, end_ms)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        for span in spans:
            stream.write(span.model_dump_json() + "\n")
    return len(spans)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="trace name (letters, numbers, hyphen, underscore)")
    parser.add_argument("--hours", type=float, default=48)
    parser.add_argument("--seconds", type=float, help="short smoke capture, overrides --hours")
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--export-only", action="store_true", help="recover an interrupted capture")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.name):
        parser.error("invalid trace name")
    duration = args.seconds if args.seconds is not None else args.hours * 3600
    if not 0 < duration <= 14 * 86400:
        parser.error("duration must be between 0 and 14 days")
    directory = ROOT / "tests" / "fixtures" / "traces"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{args.name}.raw.jsonl"
    database = ROOT / "data" / f"capture-{args.name}.sqlite"
    if output.exists() or (database.exists() and not args.export_only):
        parser.error("trace already exists; choose another name or recover with --export-only")
    if args.export_only and not database.exists():
        parser.error("no capture database to recover")
    if sys.platform != "win32" and not args.export_only:
        parser.error("live capture requires Windows")
    store = SpanStore(database)
    sampler = None
    try:
        if not args.export_only:
            settings = Settings.model_validate_json(args.settings.read_text(encoding="utf-8")) if args.settings else Settings()
            sampler = Sampler(store, lambda: settings)
            sampler.start()
            print("Local capture started. Ctrl+C stops and exports; raw titles stay local.", flush=True)
            deadline = time.monotonic() + duration
            try:
                while time.monotonic() < deadline:
                    time.sleep(min(1, max(0, deadline - time.monotonic())))
            except KeyboardInterrupt:
                pass
            sampler.stop()
            sampler = None
        count = export_raw(store, output, -(2**63), 2**63 - 1)
        print(json.dumps({"recorded_spans": count, "raw": True}))
        return 0 if count else 1
    except Exception as exc:
        print(f"Capture failed ({type(exc).__name__}); local SQLite can be recovered.", file=sys.stderr)
        return 1
    finally:
        if sampler is not None:
            sampler.stop()
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
