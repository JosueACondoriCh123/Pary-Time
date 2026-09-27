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
    ops.restore(hwnd)                                     # la persona la vuelve a abrir
    time.sleep(0.3)
    sched.tick(P + 2000)
    time.sleep(0.3)
    assert ops.is_minimized(hwnd)                         # se re-minimiza
    sched.abort(b.block_id, P + MIN)
    time.sleep(0.3)
    assert not ops.is_minimized(hwnd) and ops.exists(hwnd)   # restaurada, nunca cerrada


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
