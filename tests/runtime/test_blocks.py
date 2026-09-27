"""Bloques, sorteo y revelación. Usa el journal real y un ExperimentProvider de verdad."""
from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.contracts import Arm, Assignment, BlockConfirmed, Moderator, Settings, permuted_arm
from core.interfaces import ActiveExperiment, AppContext
from core.journal import Journal
from core.runtime import build

DATE = "2026-09-28"
DATE_2 = "2026-09-29"
NOW = 1_000_000_000_000
START = 2_000_000_000_000
SEED = "11" * 32
EXPERIMENT_ID = "exp_b1"
LABEL = "LABEL-b1-SECRET"
TARGET = "TARGET-b1-SECRET"
PATTERN = "MATCH-b1-SECRET"
STEP = "STEP-b1-SECRET"
BLOCK_ID = re.compile(r"^blk_[0-9a-f]{12}$")


class ManualClock:
    def __init__(self, now_ms: int):
        self.now = now_ms

    def now_ms(self) -> int:
        return self.now


class FixedExperiments:
    """Implementa ExperimentProvider con un experimento fijo. No es un mock."""

    def __init__(self, experiment: ActiveExperiment | None = None):
        self.experiment = experiment

    def active(self) -> ActiveExperiment | None:
        return self.experiment

    def after_outcome(self, outcome) -> None:
        return None


def experiment(treatment: Arm = Arm.primer_paso, moderator: Moderator | None = None) -> ActiveExperiment:
    return ActiveExperiment(EXPERIMENT_ID, treatment, moderator, n_per_arm=8, seed_hex=SEED)


def body(date: str, start: int, kind: str = "escritura", label: str = "escribir",
         target: str = "nota.txt", pattern: str = "code.exe") -> dict:
    return {
        "local_date": date,
        "planned_start_ms": start,
        "planned_minutes": 45,
        "task_kind": kind,
        "task_label": label,
        "target": {"kind": "file", "value": target},
        "work_matchers": [{"field": "process", "pattern": pattern}],
    }


def client_for(service):
    app = FastAPI()
    app.state.ctx = service.ctx
    app.include_router(service.router)
    return TestClient(app)


@pytest.fixture
def runtime(tmp_path):
    clock = ManualClock(NOW)
    ctx = AppContext(Journal(tmp_path / "journal.jsonl"), Settings, tmp_path, experiments=FixedExperiments())
    service = build(ctx, clock)
    yield service, clock
    service.stop()


def _pairs(journal: Journal) -> list[tuple[dict, dict]]:
    events = [event for event in journal.events()
              if event["kind"] in ("block_confirmed", "assignment")]
    assert len(events) % 2 == 0
    pairs = []
    for index in range(0, len(events), 2):
        confirmed, assigned = events[index], events[index + 1]
        assert confirmed["kind"] == "block_confirmed"
        assert assigned["kind"] == "assignment"
        assert confirmed["payload"]["block_id"] == assigned["payload"]["block_id"]
        pairs.append((confirmed["payload"], assigned["payload"]))
    return pairs


def test_crud_lists_cancelled_blocks_and_keeps_instances_apart(runtime, tmp_path):
    service, _clock = runtime
    with client_for(service) as client:
        created = []
        for offset, label in ((300, "c"), (100, "a"), (200, "b")):
            response = client.post("/blocks", json=body(DATE, START + offset, label=label))
            assert response.status_code == 201
            view = response.json()
            assert BLOCK_ID.match(view["block_id"])
            assert view["status"] == "planned" and view["created_ms"] == NOW
            assert view["arm_revealed"] is None and view["experiment_id"] is None
            assert view["needs_first_step"] is False
            created.append(view)

        listed = client.get("/blocks", params={"date": DATE}).json()
        assert [item["task_label"] for item in listed] == ["a", "b", "c"]

        edited = client.patch(f"/blocks/{created[1]['block_id']}", json={"task_label": "a2"})
        assert edited.status_code == 200
        assert edited.json()["task_label"] == "a2"
        assert edited.json()["planned_minutes"] == 45

        cancelled = client.delete(f"/blocks/{created[2]['block_id']}")
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        labels = client.get("/blocks", params={"date": DATE}).json()
        assert [(item["task_label"], item["status"]) for item in labels] == [
            ("a2", "planned"), ("b", "cancelled"), ("c", "planned")]

        missing = "blk_" + "ab" * 6
        assert client.patch(f"/blocks/{missing}", json={"task_label": "x"}).status_code == 404
        assert client.delete(f"/blocks/{missing}").status_code == 404
        assert client.post("/blocks/confirm", json={"local_date": "2026-01-01"}).json() == []
        assert list(service.ctx.journal.events()) == []

        confirmed = client.post("/blocks/confirm", json={"local_date": DATE}).json()
        assert [item["status"] for item in confirmed] == ["confirmed", "cancelled", "confirmed"]
        assert len(_pairs(service.ctx.journal)) == 2
        again = client.post("/blocks/confirm", json={"local_date": DATE})
        assert again.status_code == 200 and len(_pairs(service.ctx.journal)) == 2
        assert service.ctx.journal.verify() == 4

    other_dir = tmp_path / "other"
    other = build(AppContext(Journal(other_dir / "journal.jsonl"), Settings, other_dir), ManualClock(NOW))
    try:
        with client_for(other) as second:
            assert second.get("/blocks", params={"date": DATE}).json() == []
    finally:
        other.stop()


def test_confirmed_block_cannot_be_edited_or_cancelled(runtime):
    service, _clock = runtime
    with client_for(service) as client:
        block_id = client.post("/blocks", json=body(DATE, START)).json()["block_id"]
        client.post("/blocks/confirm", json={"local_date": DATE})
        assert client.patch(f"/blocks/{block_id}", json={"task_label": "nuevo"}).status_code == 409
        assert client.delete(f"/blocks/{block_id}").status_code == 409
        assert client.get("/blocks", params={"date": DATE}).json()[0]["status"] == "confirmed"


def test_draw_matches_permuted_arm_and_each_assignment_follows_its_confirmation(runtime):
    service, _clock = runtime
    service.ctx.experiments.experiment = experiment()
    with client_for(service) as client:
        for index in range(4):
            client.post("/blocks", json=body(DATE, START + index * 60_000, label=f"t{index}"))
        client.post("/blocks/confirm", json={"local_date": DATE})

    pairs = _pairs(service.ctx.journal)
    assert len(pairs) == 4
    for draw_index, (_confirmed, assigned) in enumerate(pairs):
        payload = Assignment.model_validate(assigned)
        assert payload.experiment_id == EXPERIMENT_ID
        assert payload.draw_index == draw_index
        assert payload.arm == permuted_arm(SEED, EXPERIMENT_ID, draw_index, Arm.primer_paso)
        BlockConfirmed.model_validate(_confirmed)
    assert service.ctx.journal.verify() == 8


def test_draw_index_continues_across_separately_confirmed_days(runtime):
    service, _clock = runtime
    service.ctx.experiments.experiment = experiment(Arm.abrir_trabajo)
    with client_for(service) as client:
        for index in range(2):
            client.post("/blocks", json=body(DATE, START + index, label=f"d1-{index}"))
        client.post("/blocks/confirm", json={"local_date": DATE})
        for index in range(2):
            client.post("/blocks", json=body(DATE_2, START + index, label=f"d2-{index}"))
        client.post("/blocks/confirm", json={"local_date": DATE_2})

    indices = [Assignment.model_validate(assigned).draw_index for _confirmed, assigned in _pairs(service.ctx.journal)]
    assert indices == [0, 1, 2, 3]


def test_ineligible_blocks_and_baseline_do_not_consume_draw_indices(runtime):
    service, _clock = runtime
    moderator = Moderator(kind="task_kind", value="escritura")
    with client_for(service) as client:
        client.post("/blocks", json=body(DATE, START, label="base"))
        client.post("/blocks", json=body(DATE, START + 1, kind="lectura", label="base-2"))
        client.post("/blocks/confirm", json={"local_date": DATE})
        baseline = [Assignment.model_validate(assigned) for _confirmed, assigned in _pairs(service.ctx.journal)]
        assert [(item.arm, item.experiment_id, item.draw_index) for item in baseline] == [
            (Arm.control, None, None), (Arm.control, None, None)]

        service.ctx.experiments.experiment = experiment(Arm.cuenta_regresiva, moderator)
        client.post("/blocks", json=body(DATE_2, START, kind="escritura", label="si"))
        client.post("/blocks", json=body(DATE_2, START + 1, kind="lectura", label="no"))
        client.post("/blocks", json=body(DATE_2, START + 2, kind="escritura", label="si-2"))
        client.post("/blocks/confirm", json={"local_date": DATE_2})

    day_2 = _pairs(service.ctx.journal)[2:]
    expected = [
        (Arm.control, None, None) if kind == "lectura" else
        (permuted_arm(SEED, EXPERIMENT_ID, draw, Arm.cuenta_regresiva), EXPERIMENT_ID, draw)
        for kind, draw in (("escritura", 0), ("lectura", None), ("escritura", 1))
    ]
    got = [(Assignment.model_validate(assigned).arm,
            Assignment.model_validate(assigned).experiment_id,
            Assignment.model_validate(assigned).draw_index) for _confirmed, assigned in day_2]
    assert got == expected


def test_journal_never_contains_user_text(runtime):
    service, _clock = runtime
    service.ctx.experiments.experiment = experiment()
    with client_for(service) as client:
        for index in range(4):
            client.post("/blocks", json=body(
                DATE, START + index, label=LABEL, target=TARGET, pattern=PATTERN))
        views = client.post("/blocks/confirm", json={"local_date": DATE}).json()
        primer = next(item for item in views if item["arm_revealed"] == "primer_paso")
        saved = client.post(f"/blocks/{primer['block_id']}/first_step", json={"text": STEP})
        assert saved.status_code == 200 and saved.json()["first_step"] == STEP

    journal_text = service.ctx.journal.path.read_text(encoding="utf-8")
    for secret in (LABEL, TARGET, PATTERN, STEP):
        assert secret not in journal_text
    assert service.ctx.journal.verify() == 8


def test_arm_stays_hidden_until_start_except_primer_paso(runtime):
    service, clock = runtime
    service.ctx.experiments.experiment = experiment()
    with client_for(service) as client:
        for index in range(4):
            client.post("/blocks", json=body(DATE, START + index * 60_000, label=f"r{index}"))
        before = client.post("/blocks/confirm", json={"local_date": DATE}).json()
        primers = [item for item in before if item["arm_revealed"] == "primer_paso"]
        hidden = [item for item in before if item["arm_revealed"] is None]
        assert primers and hidden
        assert all(item["needs_first_step"] for item in primers)
        assert all(item["experiment_id"] == EXPERIMENT_ID for item in before)
        assert all(item["planned_start_ms"] > NOW for item in hidden)

        clock.now = hidden[0]["planned_start_ms"]
        at_start = {item["block_id"]: item
                    for item in client.get("/blocks", params={"date": DATE}).json()}
        revealed = at_start[hidden[0]["block_id"]]
        still_hidden = at_start[hidden[-1]["block_id"]]
        assert revealed["arm_revealed"] == "control"
        assert still_hidden["planned_start_ms"] > clock.now
        assert still_hidden["arm_revealed"] is None

        clock.now = max(item["planned_start_ms"] for item in before)
        after = {item["block_id"]: item["arm_revealed"]
                 for item in client.get("/blocks", params={"date": DATE}).json()}
        for _confirmed, assigned in _pairs(service.ctx.journal):
            assert after[assigned["block_id"]] == assigned["arm"]


def test_first_step_is_rejected_unless_the_arm_is_primer_paso(runtime):
    service, _clock = runtime
    service.ctx.experiments.experiment = experiment()
    with client_for(service) as client:
        for index in range(4):
            client.post("/blocks", json=body(DATE, START + index, label=f"p{index}"))
        views = client.post("/blocks/confirm", json={"local_date": DATE}).json()
        primer = next(item for item in views if item["arm_revealed"] == "primer_paso")
        other = next(item for item in views if item["arm_revealed"] is None)
        assert client.post(f"/blocks/{other['block_id']}/first_step",
                           json={"text": "no toca"}).status_code == 409
        assert client.post("/blocks/blk_0123456789ab/first_step", json={"text": "no"}).status_code == 404
        saved = client.post(f"/blocks/{primer['block_id']}/first_step", json={"text": "abrir el archivo"})
        assert saved.status_code == 200
        assert saved.json()["needs_first_step"] is False
        assert saved.json()["arm_revealed"] == "primer_paso"
        assert saved.json()["first_step"] == "abrir el archivo"
