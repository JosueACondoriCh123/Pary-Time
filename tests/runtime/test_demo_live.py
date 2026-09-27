"""El script de la demo en vivo no toca datos reales ni el sorteo."""
from pathlib import Path

import pytest

from core.contracts import Arm
from core.journal import Journal, LoopLock
from tools.demo_live import DemoDirError, assert_demo_dir, main, parse_in, prepare


def test_parse_in_accepts_the_demo_clock():
    assert parse_in("2m") == 120_000
    assert parse_in("30s") == 30_000
    with pytest.raises(DemoDirError):
        parse_in("2")


def test_prepare_seals_the_requested_arm_without_drawing(tmp_path):
    view = prepare(tmp_path / "demo-live", 120_000, Arm.retrasar_distracciones, now_ms=1_700_000_000_000)
    assert view.block_id.startswith("blk_") and len(view.block_id) == 16
    assert view.status == "confirmed"
    assert view.experiment_id is None
    assert view.planned_start_ms == 1_700_000_000_000 + 120_000
    # Antes de la hora el brazo forzado sigue oculto. La cuenta regresiva es del overlay, no de la API.
    assert view.arm_revealed is None
    journal = Journal(tmp_path / "demo-live" / "journal.jsonl")
    kinds = [event["kind"] for event in journal.events()]
    assert kinds == ["block_confirmed", "assignment"]
    assigned = list(journal.events())[1]["payload"]
    assert assigned["arm"] == "retrasar_distracciones"
    assert assigned["experiment_id"] is None and assigned["draw_index"] is None
    text = journal.path.read_text(encoding="utf-8")
    assert "Demo en vivo" not in text and "nde1-demo" not in text
    assert (tmp_path / "demo-live" / "DATA_LABEL").read_text(encoding="utf-8").strip() == "sintetico"
    assert journal.verify() == 2


def test_real_data_locations_and_an_unmarked_journal_are_refused(tmp_path):
    real = tmp_path / "AppData" / "Roaming" / "Consejo N-de-1" / "data"
    real.mkdir(parents=True)
    with pytest.raises(DemoDirError):
        prepare(real, 1000, Arm.control, now_ms=1_700_000_000_000,
                roots=[(tmp_path / "AppData" / "Roaming" / "Consejo N-de-1").resolve()])
    unmarked = tmp_path / "viejo"
    unmarked.mkdir()
    (unmarked / "journal.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(DemoDirError):
        assert_demo_dir(unmarked, roots=[])
    dev = tmp_path / "repo"
    dev.mkdir()
    (dev / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    with pytest.raises(DemoDirError):
        assert_demo_dir(dev / "data", roots=[])
    assert main(["--data-dir", str(unmarked), "--in", "2m", "--arm", "retrasar_distracciones"]) == 2


def test_a_running_core_blocks_the_demo_script(tmp_path):
    path = tmp_path / "demo-live"
    path.mkdir()
    (path / "DATA_LABEL").write_text("sintetico\n", encoding="utf-8")
    lock = LoopLock(path / "core.lock")
    lock.acquire()
    try:
        with pytest.raises(DemoDirError):
            prepare(path, 1000, Arm.cuenta_regresiva, now_ms=1_700_000_000_000, roots=[])
    finally:
        lock.release()


def test_cli_writes_under_the_asked_directory(tmp_path, capsys):
    target = tmp_path / "demo-live"
    assert main(["--data-dir", str(target), "--in", "2m", "--arm", "retrasar_distracciones",
                 "--label", "Tesis cap. 3"]) == 0
    out = capsys.readouterr().out
    assert "retrasar_distracciones" in out and "DATA_LABEL=sintetico" in out
    assert Path(target / "runtime.sqlite").exists()
    journal = (target / "journal.jsonl").read_text(encoding="utf-8")
    assert "Tesis cap. 3" not in journal


def test_primer_paso_can_carry_a_first_step_that_stays_out_of_the_journal(tmp_path):
    view = prepare(tmp_path / "demo-live", 60_000, Arm.primer_paso, now_ms=1_700_000_000_000,
                   first_step="Abrir el archivo")
    assert view.arm_revealed == Arm.primer_paso
    assert view.needs_first_step is False and view.first_step == "Abrir el archivo"
    text = (tmp_path / "demo-live" / "journal.jsonl").read_text(encoding="utf-8")
    assert "Abrir el archivo" not in text
    assert main(["--data-dir", str(tmp_path / "otra"), "--in", "2m", "--arm", "control",
                 "--first-step", "no"]) == 2
