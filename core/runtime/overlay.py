"""Qué dibuja el overlay (B2). Funciones puras: mismo input, mismo output.

  * `cuenta_regresiva`: desde P − 3 min "«tarea» · arrancás en m:ss"; después de P "«tarea» · llevás N min".
    Limitación anotada: mostrarlo 3 min antes revela la condición antes de P (brief-b lo pide así).
  * `primer_paso`: desde P muestra el paso escrito la noche anterior.
  * Se esconden (y quedan escondidos) cuando la ventana activa es trabajo por 60 s seguidos, cuando el bloque
    tiene outcome final, si se abortó o tras la salida de emergencia.
"""
from __future__ import annotations

from core.contracts import ActivitySpan, Arm, Block, Category, OverlayState, Settings
from core.interfaces import Categorize

COUNTDOWN_LEAD_MS = 180_000
WORK_STREAK_TO_HIDE_S = 60
HIDDEN = OverlayState(visible=False)


def work_streak_s(spans: list[ActivitySpan], block: Block, settings: Settings, categorize: Categorize,
                  now_ms: int) -> float:
    """Segundos seguidos de trabajo que terminan en `now_ms` (tramos contiguos, sin inactividad ni bloqueo)."""
    total, cursor = 0.0, now_ms
    for s in sorted(spans, key=lambda x: x.start_ms, reverse=True):
        if s.end_ms < cursor - 5_000:             # hueco (compu apagada o sin muestras): corta la racha
            break
        if s.idle or s.locked or categorize(s, block, settings) != Category.work:
            break
        total += (min(s.end_ms, now_ms) - s.start_ms) / 1000
        cursor = s.start_ms
    return max(total, 0.0)


def _mmss(ms: int) -> str:
    s = max(ms, 0) // 1000
    return f"{s // 60}:{s % 60:02d}"


def overlay_for(block: Block, arm: Arm, now_ms: int, *, hidden: bool) -> OverlayState:
    P = block.planned_start_ms
    if hidden or block.aborted or arm not in (Arm.cuenta_regresiva, Arm.primer_paso):
        return HIDDEN
    base = dict(block_id=block.block_id, task_label=block.task_label, planned_start_ms=P)
    if arm == Arm.cuenta_regresiva:
        if now_ms < P - COUNTDOWN_LEAD_MS:
            return HIDDEN
        text = (f"{block.task_label} · arrancás en {_mmss(P - now_ms)}" if now_ms < P
                else f"{block.task_label} · llevás {(now_ms - P) // 60_000} min")
        return OverlayState(visible=True, kind="countdown", text=text, **base)
    if now_ms < P or not block.first_step:
        return HIDDEN
    return OverlayState(visible=True, kind="first_step", text=block.first_step, **base)
