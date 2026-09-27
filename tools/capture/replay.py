"""Evaluate a local block against a recorded trace; output derived BlockOutcome only."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.contracts import Block, BlockOutcome, Settings
from core.sensing.outcome import evaluate_block
from tools.capture.trace import load_trace


def replay_trace(source: Path, block: Block, settings: Settings,
                 now_ms: int | None = None) -> BlockOutcome:
    spans = load_trace(source)
    # Default to the actual recording end, never the computer's clock or an invented deadline.
    if now_ms is None:
        now_ms = spans[-1].end_ms if spans else block.planned_start_ms
    return evaluate_block(block, spans, now_ms, settings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="sanitized ActivitySpan JSONL")
    parser.add_argument("--block", type=Path, required=True, help="local Block JSON including work matchers")
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--now-ms", type=int, help="explicit observation time; defaults to trace end")
    parser.add_argument("--expect", type=Path, help="compare with a reviewed BlockOutcome regression fixture")
    parser.add_argument("--output", type=Path, help="new file for the derived result; never overwrites")
    args = parser.parse_args(argv)
    try:
        block = Block.model_validate_json(args.block.read_text(encoding="utf-8-sig"))
        settings = Settings.model_validate_json(args.settings.read_text(encoding="utf-8-sig")) if args.settings else Settings()
        result = replay_trace(args.source, block, settings, args.now_ms)
        if args.expect is not None:
            expected = BlockOutcome.model_validate_json(args.expect.read_text(encoding="utf-8-sig"))
            if result != expected:
                print("Replay differs from the reviewed outcome fixture.", file=sys.stderr)
                return 1
        if args.output is not None:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(result.model_dump_json() + "\n")
        print(result.model_dump_json())
    except Exception as exc:
        print(f"Replay failed ({type(exc).__name__}); check trace, block and settings.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
