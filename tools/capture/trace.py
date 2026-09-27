"""Read chronological activity fixtures without echoing private JSON on errors."""
from pathlib import Path

from core.contracts import ActivitySpan


def load_trace(source: Path) -> list[ActivitySpan]:
    spans: list[ActivitySpan] = []
    with source.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                span = ActivitySpan.model_validate_json(line)
                if span.end_ms <= span.start_ms or (spans and span.start_ms < spans[-1].end_ms):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError(f"invalid or overlapping activity span at line {number}") from None
            spans.append(span)
    return spans
