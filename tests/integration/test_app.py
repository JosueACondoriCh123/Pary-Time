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


@pytest.mark.parametrize("method,path", [("get", "/activity/today"), ("get", "/runtime/status"),
                                         ("get", "/experiments/current")])
def test_front_stubs_answer_501_until_implemented(client, method, path):
    assert getattr(client, method)(path, headers=auth()).status_code == 501


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
