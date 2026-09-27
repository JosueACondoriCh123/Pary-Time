import pytest
from fastapi.testclient import TestClient

from core.app import TOKEN_HEADER, create_app
from core.journal import Journal, JournalError, append_typed

TOKEN = "t" * 43


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path, TOKEN)) as cl:
        cl.data_dir = tmp_path
        yield cl


def auth():
    return {TOKEN_HEADER: TOKEN}


def test_health_is_open_and_reports_the_journal(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] and r.json()["journal_seq"] == 1   # app_start


def test_every_other_route_requires_the_local_token(client):
    assert client.get("/settings").status_code == 401
    assert client.get("/settings", headers={TOKEN_HEADER: "otro"}).status_code == 401
    assert client.get("/blocks", params={"date": "2026-09-29"}).status_code == 401
    assert client.get("/settings", headers=auth()).status_code == 200


def test_settings_roundtrip_journals_only_the_changed_keys(client):
    s = client.get("/settings", headers=auth()).json()
    s["raw_retention_days"] = 7
    assert client.put("/settings", json=s, headers=auth()).json()["raw_retention_days"] == 7
    ev = list(Journal(client.data_dir / "journal.jsonl").events())[-1]
    assert ev["kind"] == "settings_changed" and ev["payload"] == {"keys": ["raw_retention_days"]}


def test_journal_verify_route(client):
    assert client.get("/journal/verify", headers=auth()).json() == {"ok": True, "n_events": 1, "error": None}


def test_full_app_plans_confirms_runs_and_aborts_a_block_end_to_end(client):
    """Hito 1 por HTTP con los 4 frentes montados: B1 guarda y sortea, B2 lo corre y lo aborta, el journal
    queda verificable y sin textos del usuario. (Sin experimento activo: línea base, brazo control.)"""
    import time
    from datetime import datetime
    now = int(time.time() * 1000)
    day = datetime.fromtimestamp(now / 1000).date().isoformat()
    body = {"local_date": day, "planned_start_ms": now - 60_000, "planned_minutes": 30, "task_kind": "escritura",
            "task_label": "Etiqueta-e2e-privada", "target": {"kind": "none", "value": ""},
            "work_matchers": [{"field": "process", "pattern": "WINWORD.EXE"}]}
    created = client.post("/blocks", json=body, headers=auth())
    assert created.status_code == 201
    bid = created.json()["block_id"]
    [confirmed] = client.post("/blocks/confirm", json={"local_date": day}, headers=auth()).json()
    assert confirmed["status"] == "confirmed" and confirmed["arm_revealed"] == "control"
    st = client.get("/runtime/status", headers=auth()).json()
    assert st["active_block_id"] == bid and st["interventions_applied"] == []
    assert client.get("/runtime/overlay", headers=auth()).json()["visible"] is False
    aborted = client.post(f"/blocks/{bid}/abort", headers=auth())
    assert aborted.status_code == 200 and aborted.json()["aborted"] is True
    assert client.post(f"/blocks/{bid}/abort", headers=auth()).status_code == 409
    assert client.post("/blocks/blk_000000000000/abort", headers=auth()).status_code == 404
    kinds = [e["kind"] for e in Journal(client.data_dir / "journal.jsonl").events()]
    assert kinds[-3:] == ["block_confirmed", "assignment", "block_abort"]
    assert client.get("/journal/verify", headers=auth()).json()["ok"]
    assert "Etiqueta-e2e-privada" not in (client.data_dir / "journal.jsonl").read_text(encoding="utf-8")


def test_a_second_core_on_the_same_data_dir_is_refused(tmp_path):
    from core.journal import LoopLockError
    with TestClient(create_app(tmp_path, TOKEN)):
        with pytest.raises(LoopLockError):
            with TestClient(create_app(tmp_path, TOKEN)):
                pass


def test_append_typed_rejects_unknown_kinds_and_off_contract_payloads(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    with pytest.raises(JournalError):
        append_typed(j, "heartbeat", {})
    with pytest.raises(Exception):
        append_typed(j, "block_abort", {"block_id": "blk_1", "ts_ms": 1, "title": "WhatsApp"})
    ev = append_typed(j, "block_abort", {"block_id": "blk_1", "ts_ms": 1})
    assert ev["payload"] == {"block_id": "blk_1", "ts_ms": 1} and j.verify() == 1


def test_raw_journal_append_refuses_window_titles(tmp_path):
    with pytest.raises(JournalError, match="prohibido"):
        Journal(tmp_path / "j.jsonl").append("x", {"span": {"title": "cap3.docx"}}, "v")


def test_council_routes_are_live_and_hide_effects_without_an_experiment(client):
    assert client.get("/experiments/current", headers=auth()).json() is None
    assert client.get("/experiments", headers=auth()).json() == []
    assert len(client.get("/ledger", headers=auth()).json()) == 4


def test_sensing_routes_are_live(client):
    r = client.get("/activity/today", headers=auth())
    assert r.status_code == 200 and set(r.json()) >= {"local_date", "minutes_by_category", "sensor_running"}
