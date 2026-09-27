import json
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.contracts import BlockConfirmed, BlockOutcome, Settings
from core.interfaces import AppContext
from core.journal import Journal, append_typed
from core.sensing import build

from .conftest import P, ROOT, synthetic_span as span


@pytest.fixture
def service(tmp_path):
    ctx = AppContext(Journal(tmp_path / "journal.jsonl"), Settings, tmp_path)
    service = build(ctx)
    yield service
    service.stop()


def client_for(service):
    # No lifespan: deterministic tests load declared spans into real SQLite, without sampling.
    app = FastAPI()
    app.include_router(service.router)
    return TestClient(app)


def test_summary_has_no_titles_and_all_four_categories(service):
    rows = [span(0, 60, "chrome.exe", "youtube"), span(60, 120, "explorer.exe", ""),
            span(120, 180, idle=True), span(180, 240, "__paused__", "", idle=True)]
    for row in rows:
        service.activity.write(row)
    summary = service.summary(P + 240000)
    assert summary.minutes_by_category == dict(distraction=1, other=1, idle=1, paused=1)
    assert summary.local_date == datetime.fromtimestamp(P / 1000).date().isoformat()
    assert "title" not in summary.model_dump_json()
    assert not summary.sensor_running


def test_router_privacy_controls_validate_duration_and_are_bound_per_instance(service, tmp_path):
    other_dir = tmp_path / "other"
    other = build(AppContext(Journal(other_dir / "journal.jsonl"), Settings, other_dir))
    try:
        with client_for(service) as first, client_for(other) as second:
            assert first.get("/activity/today").status_code == 200
            for duration in (0, 481):
                assert first.post("/activity/pause", params={"minutes": duration}).status_code == 422
            paused = first.post("/activity/pause", params={"minutes": 1})
            assert paused.status_code == 200 and paused.json()["paused_until_ms"] is not None
            assert second.get("/activity/today").json()["paused_until_ms"] is None
            assert first.post("/activity/resume").json()["paused_until_ms"] is None
            assert list(service.ctx.journal.events()) == []  # sensing never writes journal events
    finally:
        other.stop()


def test_outcomes_join_declared_local_date_not_computation_time(service, block):
    outcome = BlockOutcome.model_validate_json(
        (ROOT / "contracts/examples/BlockOutcome.started.json").read_text(encoding="utf-8"))
    confirmed = BlockConfirmed(block_id=block.block_id, local_date="2026-09-29",
                               planned_start_ms=block.planned_start_ms,
                               planned_minutes=block.planned_minutes, task_kind=block.task_kind)
    # Real journal populated with contract fixtures, acting as the runtime's input to A.
    append_typed(service.ctx.journal, "block_confirmed", confirmed)
    append_typed(service.ctx.journal, "outcome", outcome.model_copy(update={"computed_ms": 0}))
    append_typed(service.ctx.journal, "outcome", outcome.model_copy(update={"block_id": "blk_orphan"}))
    with client_for(service) as client:
        result = client.get("/outcomes", params={"from_date": "2026-09-29", "to_date": "2026-09-29"})
        assert result.status_code == 200 and len(result.json()) == 1
        assert result.json()[0]["block_id"] == block.block_id
        assert client.get("/outcomes", params={"from_date": "2026-09-30", "to_date": "2026-10-01"}).json() == []
        for start, end in [("2026-02-30", "2026-03-01"), ("2026-10-01", "2026-09-29")]:
            assert client.get("/outcomes", params={"from_date": start, "to_date": end}).status_code == 422
    assert service.ctx.journal.verify() == 3


def test_day_summary_clips_at_local_midnight(service):
    midnight = datetime(2026, 9, 29).timestamp() * 1000
    row = span(0, 120, "chrome.exe", "youtube").model_copy(
        update={"start_ms": int(midnight - 60000), "end_ms": int(midnight + 60000)})
    service.activity.write(row)
    assert service.summary(int(midnight + 60000)).minutes_by_category["distraction"] == 1
