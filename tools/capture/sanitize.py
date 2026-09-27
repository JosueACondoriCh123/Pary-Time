"""Export allowlisted title tokens only. Never print raw input or validation errors."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.contracts import ActivitySpan, Settings


def sanitize_span(span: ActivitySpan, keep: list[str], settings: Settings) -> ActivitySpan:
    allowed = [token.casefold() for token in keep if token]
    if span.process.casefold() in {p.casefold() for p in settings.browser_processes}:
        allowed += [token.casefold() for token in settings.distraction_title_patterns if token]
    # Multiple approved tokens preserve work and distraction matchers in the same title.
    tokens = list(dict.fromkeys(token for token in allowed if token in span.title.casefold()))
    title = " ".join(tokens)[:512] if span.process != "__paused__" else ""
    return span.model_copy(update={"title": title})


def sanitize_file(source: Path, destination: Path, keep: list[str], settings: Settings) -> int:
    if source.resolve() == destination.resolve():
        raise ValueError("source and destination must differ")
    if destination.name.endswith(".raw.jsonl"):
        raise ValueError("sanitized output must not use the raw suffix")
    # Validate all rows before creating the result: no partial fixtures after bad input.
    sanitized = []
    with source.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                span = ActivitySpan.model_validate_json(line)
                if span.end_ms <= span.start_ms:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError(f"invalid activity span at line {number}") from None
            sanitized.append(sanitize_span(span, keep, settings))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as output:
        for span in sanitized:
            output.write(span.model_dump_json() + "\n")
    return len(sanitized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--keep", action="append", default=[])
    parser.add_argument("--settings", type=Path, help="local Settings JSON for custom distraction patterns")
    args = parser.parse_args(argv)
    destination = args.output or args.source.with_name(args.source.name.replace(".raw.jsonl", ".jsonl"))
    try:
        settings = Settings.model_validate_json(args.settings.read_text(encoding="utf-8")) if args.settings else Settings()
        count = sanitize_file(args.source, destination, args.keep, settings)
    except Exception as exc:
        # JSON/Pydantic errors can embed the original title: do not print str(exc).
        print(f"Sanitization failed ({type(exc).__name__}); check input and output files.", file=sys.stderr)
        return 1
    print(json.dumps({"sanitized_spans": count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
