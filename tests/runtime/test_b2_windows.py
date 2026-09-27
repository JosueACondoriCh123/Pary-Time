"""Intervenciones con ventanas REALES de Windows.

Se usa una ventana Tk propia con un título único (nunca el Bloc de notas de la persona, que en Windows 11 abre
pestañas en la ventana existente). La categorización es la real del Frente A: `python.exe` se declara como
"navegador" y el título único como sitio de distracción, así solo esa ventana califica.
"""
import subprocess
import sys
import time
import uuid

import pytest

from core.contracts import Arm, Settings
from core.runtime.intervention_state import InterventionState
from core.runtime.interventions import Win32Ops
from core.runtime.scheduler import Scheduler
from tests.runtime.b2_support import MIN, P, block, events, make

pytestmark = [pytest.mark.windows, pytest.mark.skipif(sys.platform != "win32", reason="solo Windows")]


@pytest.fixture
def tk_window():
    title = f"nde1-prueba-{uuid.uuid4().hex[:8]}"
    code = (f"import tkinter as tk; r = tk.Tk(); r.title({title!r}); r.geometry('240x80+40+40'); "
            "r.after(60000, r.destroy); r.mainloop()")
    proc = subprocess.Popen([sys.executable, "-c", code])
    ops = Win32Ops()
    hwnd = None
    for _ in range(100):
        hwnd = next((w.hwnd for w in ops.windows() if w.title == title), None)
        if hwnd:
            break
        time.sleep(0.1)
    assert hwnd, "la ventana Tk no apareció"
    yield title, hwnd, ops
    proc.kill()
    proc.wait(10)


def settings_for(title: str) -> Settings:
    return Settings(distraction_processes=[], browser_processes=["python.exe"], distraction_title_patterns=[title])


def test_delay_distractions_minimizes_only_our_window_and_restores_it(tmp_path, tk_window):
    title, hwnd, ops = tk_window
    b = block(1)
    sched, ctx, _ = make(tmp_path, [b], {b.block_id: Arm.retrasar_distracciones}, windows=ops,
                         settings=settings_for(title))
    sched.tick(P)
    time.sleep(0.3)
    assert ops.is_minimized(hwnd)
    assert events(ctx, "intervention")[0]["payload"]["n_windows"] == 1
    ops.restore(hwnd, ops.pid_of(hwnd))                   # la persona la vuelve a abrir
    time.sleep(0.3)
    sched.tick(P + 2000)
    time.sleep(0.3)
    assert ops.is_minimized(hwnd)                         # se re-minimiza
    sched.abort(b.block_id, P + MIN)
    time.sleep(0.3)
    assert not ops.is_minimized(hwnd) and ops.pid_of(hwnd) is not None   # restaurada, nunca cerrada


def test_a_crash_with_a_minimized_window_is_undone_on_restart(tmp_path, tk_window):
    title, hwnd, ops = tk_window
    b = block(1)
    sched, ctx, repo = make(tmp_path, [b], {b.block_id: Arm.retrasar_distracciones}, windows=ops,
                            settings=settings_for(title))
    sched.tick(P)
    time.sleep(0.3)
    assert ops.is_minimized(hwnd)
    del sched                                             # el núcleo "muere" sin revertir
    again = Scheduler(ctx, repo, InterventionState(tmp_path / "interventions.sqlite"), ops)
    assert again.recover(P + MIN) == 1
    time.sleep(0.3)
    assert not ops.is_minimized(hwnd)
    last = events(ctx, "intervention")[-1]["payload"]
    assert (last["action"], last["reason"], last["n_windows"]) == ("reverted", "recovery", 1)


def test_a_dead_window_is_not_restored_after_a_crash(tmp_path, tk_window):
    """Si la ventana minimizada murió antes de la recuperación, su hwnd puede reciclarse: no se restaura nada."""
    title, hwnd, ops = tk_window
    b = block(1)
    sched, ctx, repo = make(tmp_path, [b], {b.block_id: Arm.retrasar_distracciones}, windows=ops,
                            settings=settings_for(title))
    sched.tick(P)
    time.sleep(0.3)
    [(saved_hwnd, saved_pid)] = sched.state.minimized(b.block_id)
    assert saved_hwnd == hwnd and ops.pid_of(hwnd) == saved_pid
    assert not ops.restore(hwnd, saved_pid + 1)          # PID distinto: no la toca
    assert ops.is_minimized(hwnd)


def _kill(proc):
    if proc.poll() is None:
        proc.kill()
        proc.wait(10)


def _launch(data_dir):
    import os
    env = os.environ.copy()
    env.pop("NDE1_NO_DESKTOP", None)
    env["NDE1_TOKEN"] = "t" * 43
    root = str(__import__("pathlib").Path(__file__).resolve().parents[2])
    return subprocess.Popen(
        [sys.executable, "-m", "core", "--port", "0", "--data-dir", str(data_dir)],
        cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )


def test_terminate_process_then_relaunch_restores_and_journals_recovery(tmp_path, tk_window):
    """Mata el núcleo con TerminateProcess y, al relanzarlo, la ventana propia vuelve y el journal dice recovery."""
    from core.contracts import Assignment, BlockConfirmed, BlockCreate, Target, TaskKind, WorkMatcher
    from core.interfaces import AppContext
    from core.journal import Journal, append_typed
    from core.runtime import build

    title, hwnd, ops = tk_window
    settings = settings_for(title)
    (tmp_path / "settings.json").write_text(settings.model_dump_json(), encoding="utf-8")
    now = time.time_ns() // 1_000_000
    ctx = AppContext(Journal(tmp_path / "journal.jsonl"), lambda: settings, tmp_path)

    class Clock:
        def now_ms(self):
            return now

    service = build(ctx, Clock())
    try:
        created = service.create_block(BlockCreate(
            local_date="2026-09-27", planned_start_ms=now - 3_000, planned_minutes=25,
            task_kind=TaskKind.otro, task_label="caida", target=Target(kind="none"),
            work_matchers=[WorkMatcher(field="process", pattern="nde1-demo")],
        ))
        service.store.mark_confirmed(created.block_id)
        block = service.store.get(created.block_id).block
        append_typed(ctx.journal, "block_confirmed", BlockConfirmed(
            block_id=block.block_id, local_date=block.local_date, planned_start_ms=block.planned_start_ms,
            planned_minutes=block.planned_minutes, task_kind=block.task_kind))
        service.store.save_assignment(block.block_id, Arm.retrasar_distracciones, None, None, now)
        append_typed(ctx.journal, "assignment", Assignment(
            block_id=block.block_id, arm=Arm.retrasar_distracciones, experiment_id=None,
            draw_index=None, assigned_ms=now))
    finally:
        service.stop()

    first = _launch(tmp_path)
    try:
        minimized = False
        for _ in range(80):
            if ops.is_minimized(hwnd):
                minimized = True
                break
            time.sleep(0.25)
        assert minimized, "el núcleo no minimizó la ventana de prueba"
    finally:
        _kill(first)

    second = _launch(tmp_path)
    try:
        recovered = None
        deadline = time.time() + 20
        while time.time() < deadline:
            recovered = next((event["payload"] for event in Journal(tmp_path / "journal.jsonl").events()
                              if event["kind"] == "intervention" and event["payload"]["reason"] == "recovery"),
                             None)
            if recovered:
                break
            time.sleep(0.25)
        assert recovered is not None
        assert recovered["action"] == "reverted" and recovered["n_windows"] >= 1
        assert ops.pid_of(hwnd) is not None
    finally:
        _kill(second)
    assert Journal(tmp_path / "journal.jsonl").verify() > 0

