"""Contract examples and explicitly synthetic observations; no simulated native APIs."""
import json
from pathlib import Path

import pytest

from core.contracts import ActivitySpan, Block, Settings

ROOT = Path(__file__).resolve().parents[2]
P = 1790686800000


def synthetic_span(start, end, process="WINWORD.EXE", title="cap3", idle=False, locked=False):
    return ActivitySpan(start_ms=P + round(start * 1000), end_ms=P + round(end * 1000),
                        process=process, title=title, idle=idle, locked=locked)


@pytest.fixture
def block():
    return Block.model_validate_json((ROOT / "contracts/examples/Block.json").read_text(encoding="utf-8"))


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def example_spans():
    return [ActivitySpan.model_validate(item) for item in json.loads(
        (ROOT / "contracts/examples/ActivitySpan.list.json").read_text(encoding="utf-8"))]
