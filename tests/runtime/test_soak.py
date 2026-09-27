"""Soak acelerado: 48 h de ticks del scheduler, sin dormir 48 h ni tocar el escritorio."""
import logging

from core.contracts import Arm
from core.runtime.privacy_log import attach_runtime_log, detach_runtime_log
from core.runtime.scheduler import Scheduler
from tests.runtime.b2_support import MIN, P, block, make

HOUR = 60 * MIN
SECRET = "ETIQUETA-SOAK-99"
PATH = r"C:\Users\HP\Secreto\tarea.docx"


def test_forty_eight_hours_keep_one_intervention_and_leave_no_trace_of_the_user(tmp_path):
    blocks = [block(i + 1, start=P + i * 6 * HOUR, label=SECRET, first_step=SECRET) for i in range(8)]
    arms = {b.block_id: Arm.retrasar_distracciones for b in blocks}
    sched, ctx, _ = make(tmp_path, blocks, arms)
    handler = attach_runtime_log(tmp_path)
    logging.getLogger("core.runtime.scheduler").warning("no se pudo abrir %s", PATH)
    try:
        t = P
        end = P + 48 * HOUR
        while t <= end:
            sched.tick(t)
            assert len(sched.state.unreverted()) <= 1
            t += 5 * MIN
        assert sched.state.unreverted() == []
        assert ctx.journal.verify() >= 1
        journal = (tmp_path / "journal.jsonl").read_text(encoding="utf-8")
        log_text = (tmp_path / "runtime.log").read_text(encoding="utf-8")
        assert SECRET not in journal and SECRET not in log_text
        assert PATH not in log_text and "[ruta]" in log_text
    finally:
        detach_runtime_log(handler)


def test_the_scheduler_thread_stops(tmp_path):
    sched, _, _ = make(tmp_path, [], {})
    assert isinstance(sched, Scheduler)
    sched.start()
    sched.stop()
    assert sched._thread is not None and not sched._thread.is_alive()
