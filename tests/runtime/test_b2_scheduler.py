"""Scheduler de B2 con el evaluate_block y el categorize reales del Frente A. Datos SINTÉTICOS."""
from datetime import datetime

import pytest

from core.contracts import Arm, BlockStatus, Settings, Target
from core.runtime.interventions import WinInfo, select_distractions
from core.runtime.intervention_state import InterventionState
from core.runtime.scheduler import BlockNotActive, Scheduler
from core.sensing.categorize import categorize
from tests.runtime.b2_support import MIN, P, RecordingOpener, block, distraction, events, make, work


def iv(ctx):
    return [(e["payload"]["block_id"], e["payload"]["action"], e["payload"]["reason"]) for e in events(ctx, "intervention")]


def test_countdown_block_lifecycle_until_the_outcome(tmp_path):
    b = block(1)
    spans = [distraction(P, 5), work(P + 5 * MIN, 16)]
    sched, ctx, repo = make(tmp_path, [b], {b.block_id: Arm.cuenta_regresiva}, spans)
    sched.tick(P - 4 * MIN)
    assert not sched.overlay(P - 4 * MIN).visible and not iv(ctx)
    ov = sched.overlay(P - 2 * MIN)
    assert ov.visible and ov.kind == "countdown" and ov.text.endswith("arrancás en 2:00")
    sched.tick(P + 1000)
    assert repo.get(b.block_id).status == BlockStatus.running
    assert iv(ctx) == [(b.block_id, "applied", "block_start")]
    assert sched.overlay(P + 3 * MIN).text.endswith("llevás 3 min")
    sched.tick(P + 21 * MIN + 1000)
    [out] = events(ctx, "outcome")
    assert out["payload"]["status"] == "started" and out["payload"]["latency_s"] == 300
    assert iv(ctx)[-1] == (b.block_id, "reverted", "work_run_reached")
    assert repo.get(b.block_id).status == BlockStatus.started
    assert [o.block_id for o in ctx.experiments.outcomes] == [b.block_id]
    sched.tick(P + 30 * MIN)                                   # final: no se vuelve a escribir nada
    assert len(events(ctx, "outcome")) == 1 and not sched.overlay(P + 30 * MIN).visible


def test_first_seen_late_in_the_window_is_a_device_wake(tmp_path):
    b = block(1)
    sched, ctx, _ = make(tmp_path, [b], {b.block_id: Arm.cuenta_regresiva})
    sched.tick(P + 10 * MIN)
    assert iv(ctx) == [(b.block_id, "applied", "device_wake")]


def test_computer_off_the_whole_window_is_device_off_and_never_intervened(tmp_path):
    b = block(1)
    sched, ctx, repo = make(tmp_path, [b], {b.block_id: Arm.cuenta_regresiva})
    sched.tick(P + 91 * MIN)
    assert not iv(ctx)
    assert events(ctx, "outcome")[0]["payload"]["status"] == "device_off"
    assert repo.get(b.block_id).status == BlockStatus.device_off


def test_open_work_without_target_fails_once_and_keeps_the_arm(tmp_path):
    b = block(1)
    sched, ctx, _ = make(tmp_path, [b], {b.block_id: Arm.abrir_trabajo})
    for t in (P, P + 2000, P + 4000):
        sched.tick(t)
    assert iv(ctx) == [(b.block_id, "failed", "error")]


def test_open_work_opens_the_target_exactly_once(tmp_path):
    doc = tmp_path / "cap3.docx"
    doc.write_bytes(b"x")
    b = block(1, target=Target(kind="file", value=str(doc)))
    opener = RecordingOpener()
    sched, ctx, _ = make(tmp_path, [b], {b.block_id: Arm.abrir_trabajo}, opener=opener)
    for t in (P, P + 2000, P + 60_000):
        sched.tick(t)
    assert opener.opened == [str(doc)] and iv(ctx) == [(b.block_id, "applied", "block_start")]


def test_a_new_block_takes_over_the_single_active_intervention(tmp_path):
    b1 = block(1, first_step="Abrir el doc y escribir el título")
    b2 = block(2, start=P + 50 * MIN)
    sched, ctx, repo = make(tmp_path, [b1, b2], {b1.block_id: Arm.primer_paso, b2.block_id: Arm.cuenta_regresiva})
    sched.tick(P)
    assert sched.overlay(P + MIN).kind == "first_step"
    sched.tick(P + 50 * MIN)
    assert iv(ctx) == [(b1.block_id, "applied", "block_start"), (b1.block_id, "reverted", "block_start"),
                       (b2.block_id, "applied", "block_start")]
    assert repo.get(b1.block_id).status == BlockStatus.running            # b1 se sigue evaluando
    assert sched.overlay(P + 51 * MIN).block_id == b2.block_id


def test_abort_reverts_logs_and_keeps_evaluating_the_block(tmp_path):
    b = block(1)
    sched, ctx, repo = make(tmp_path, [b], {b.block_id: Arm.cuenta_regresiva}, [work(P + 40 * MIN, 16)])
    sched.tick(P)
    aborted = sched.abort(b.block_id, P + 5 * MIN)
    assert aborted.aborted and iv(ctx)[-1] == (b.block_id, "reverted", "abort")
    assert events(ctx, "block_abort")[0]["payload"] == {"block_id": b.block_id, "ts_ms": P + 5 * MIN}
    sched.tick(P + 10 * MIN)
    assert len(iv(ctx)) == 2                                               # no se reaplica
    sched.tick(P + 57 * MIN)
    assert events(ctx, "outcome")[0]["payload"]["latency_s"] == 2400       # intención de tratar
    with pytest.raises(BlockNotActive):
        sched.abort(b.block_id, P + 58 * MIN)


def test_a_tick_gap_does_not_apply_the_intervention_twice(tmp_path):
    """Una suspensión de varios minutos no vuelve a aplicar: el brazo ya está applied."""
    b = block(1)
    sched, ctx, _ = make(tmp_path, [b], {b.block_id: Arm.retrasar_distracciones})
    sched.tick(P)
    sched.tick(P + 10 * MIN)
    assert iv(ctx) == [(b.block_id, "applied", "block_start")]


def test_midnight_handoff_keeps_a_single_active_intervention(tmp_path):
    late = int(datetime(2026, 9, 29, 23, 50).timestamp() * 1000)
    early = int(datetime(2026, 9, 30, 0, 20).timestamp() * 1000)
    b1 = block(1, start=late)
    b2 = block(2, start=early).model_copy(update={"local_date": "2026-09-30"})
    sched, ctx, repo = make(tmp_path, [b1, b2],
                            {b1.block_id: Arm.retrasar_distracciones, b2.block_id: Arm.cuenta_regresiva})
    sched.tick(late)
    sched.tick(early)
    assert iv(ctx) == [(b1.block_id, "applied", "block_start"), (b1.block_id, "reverted", "block_start"),
                       (b2.block_id, "applied", "block_start")]
    assert repo.get(b1.block_id).status == BlockStatus.running
    assert sched.overlay(early + MIN).block_id == b2.block_id


def test_recovery_restores_and_then_reapplies_only_what_is_safe(tmp_path):
    b1, b2 = block(1), block(2, start=P + 200 * MIN)
    sched, ctx, repo = make(tmp_path, [b1], {b1.block_id: Arm.retrasar_distracciones})
    sched.tick(P)
    assert iv(ctx) == [(b1.block_id, "applied", "block_start")]
    # "Caída": un scheduler nuevo sobre el mismo estado local y el mismo journal.
    again = Scheduler(ctx, repo, InterventionState(tmp_path / "interventions.sqlite"), sched.win, opener=sched.opener)
    assert again.recover(P + MIN) == 1
    assert iv(ctx)[-1] == (b1.block_id, "reverted", "recovery")
    again.tick(P + MIN + 2000)
    assert iv(ctx)[-1] == (b1.block_id, "reapplied", "recovery")
    assert again.recover(P + 2 * MIN) == 1 and again.recover(P + 3 * MIN) == 0


def test_emergency_release_stops_reminimizing_for_that_block(tmp_path):
    b = block(1)
    sched, ctx, _ = make(tmp_path, [b], {b.block_id: Arm.retrasar_distracciones})
    sched.tick(P)
    st = sched.emergency_release(P + MIN)
    assert st.emergency_released and iv(ctx)[-1] == (b.block_id, "reverted", "emergency_release")
    n = len(iv(ctx))
    for t in range(2, 10):
        sched.tick(P + t * MIN)
    assert len(iv(ctx)) == n


def test_overlay_hides_after_a_minute_of_real_work_and_stays_hidden(tmp_path):
    b = block(1, first_step="Escribir una oración fea")
    spans = [distraction(P, 3), work(P + 3 * MIN, 1.2), distraction(P + 4.2 * MIN, 5)]
    sched, ctx, _ = make(tmp_path, [b], {b.block_id: Arm.primer_paso}, spans)
    sched.tick(P)
    assert sched.overlay(P + 2 * MIN).visible
    assert not sched.overlay(P + 4.1 * MIN).visible                         # 66 s de trabajo seguido
    assert not sched.overlay(P + 6 * MIN).visible                           # volvió a distraerse: sigue oculto


def test_control_blocks_are_evaluated_without_touching_anything(tmp_path):
    b = block(1)
    sched, ctx, _ = make(tmp_path, [b], {b.block_id: Arm.control}, [work(P + 2 * MIN, 15)])
    sched.tick(P)
    sched.tick(P + 17 * MIN + 1000)
    assert not iv(ctx) and events(ctx, "outcome")[0]["payload"]["latency_s"] == 120


def test_journal_never_carries_labels_targets_or_first_steps(tmp_path):
    doc = tmp_path / "secreto-XYZ.docx"
    doc.write_bytes(b"x")
    b1 = block(1, label="Etiqueta-privada-123", target=Target(kind="file", value=str(doc)))
    b2 = block(2, start=P + 100 * MIN, first_step="Paso-privado-456")
    sched, ctx, _ = make(tmp_path, [b1, b2], {b1.block_id: Arm.abrir_trabajo, b2.block_id: Arm.primer_paso},
                         [work(P + MIN, 16), work(P + 101 * MIN, 16)])
    for t in (P, P + 17 * MIN + 1000, P + 100 * MIN, P + 118 * MIN):
        sched.tick(t)
    sched.overlay(P + 100 * MIN)
    text = (tmp_path / "journal.jsonl").read_text(encoding="utf-8")
    for secret in ("Etiqueta-privada-123", "secreto-XYZ", "Paso-privado-456", "WINWORD", "cap3"):
        assert secret not in text
    assert ctx.journal.verify() == len(events(ctx))


def test_distraction_selection_respects_the_whitelist():
    wins = [WinInfo(1, 11, "WhatsApp.exe", "WhatsApp"), WinInfo(2, 12, "chrome.exe", "YouTube - Google Chrome"),
            WinInfo(3, 12, "chrome.exe", "Overleaf - Google Chrome"), WinInfo(4, 13, "WINWORD.EXE", "cap3.docx - Word")]
    picked = select_distractions(wins, Settings(), categorize)
    assert [w.hwnd for w in picked] == [1, 2]
    s = Settings(whitelist_processes=["whatsapp.exe"])
    assert [w.hwnd for w in select_distractions(wins, s, categorize)] == [2]


def test_whatsapp_desktop_and_cloaked_youtube_count_other_cloaked_windows_do_not():
    wins = [WinInfo(1, 1, "WhatsApp.Root.exe", "WhatsApp"),
            WinInfo(2, 2, "ApplicationFrameHost.exe", "WhatsApp", cloaked=True),
            WinInfo(3, 3, "chrome.exe", "lofi - YouTube", cloaked=True),
            WinInfo(4, 4, "msedge.exe", "YouTube", cloaked=True),
            WinInfo(5, 5, "ApplicationFrameHost.exe", "B&O Audio Control", cloaked=True),
            WinInfo(6, 6, "msedgewebview2.exe", "WhatsApp")]
    picked = select_distractions(wins, Settings(), categorize)
    assert [w.hwnd for w in picked] == [1, 2, 3, 4]
    white = Settings(whitelist_processes=["WhatsApp.exe"])
    assert [w.hwnd for w in select_distractions(wins, white, categorize)] == [3, 4]


def test_synthetic_demo_shows_the_countdown_for_delay_distractions(tmp_path):
    b = block(1)
    sched, _, _ = make(tmp_path, [b], {b.block_id: Arm.retrasar_distracciones})
    assert not sched.overlay(P - 2 * MIN).visible
    (tmp_path / "DATA_LABEL").write_text("sintetico\n", encoding="utf-8")
    shown = sched.overlay(P - 2 * MIN)
    assert shown.visible and shown.kind == "countdown" and shown.text.endswith("arrancás en 2:00")


def test_our_own_app_the_core_and_the_desktop_are_never_distractions():
    import os
    from core.runtime.interventions import PROTECTED_PROCESSES
    s = Settings(distraction_processes=["Consejo N-de-1.exe", "explorer.exe", "python.exe"],
                 browser_processes=["electron.exe"], distraction_title_patterns=["consejo"])
    wins = [WinInfo(1, 21, "Consejo N-de-1.exe", "Consejo N-de-1"), WinInfo(2, 22, "electron.exe", "Consejo N-de-1"),
            WinInfo(3, 23, "explorer.exe", "Descargas"), WinInfo(4, os.getpid(), "python.exe", "núcleo")]
    assert select_distractions(wins, s, categorize) == []
    assert "nde1-core.exe" in PROTECTED_PROCESSES
