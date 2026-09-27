"""Generador mínimo de tramos SINTÉTICOS (respaldo de `tools/capture/synth.py` del Frente A).

Cumple `core.interfaces.SynthDay` con lo justo para que la simulación corra: por bloque, distracción u otra app
hasta la latencia sorteada, y después 20 min de trabajo que coincide con su primer matcher. Mañanas lentas,
tardes rápidas, ~10% de mañanas sin arranque y ~5% de bloques con la compu apagada. Títulos genéricos.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from random import Random

from core.contracts import ActivitySpan, Block

MIN = 60_000


def _span(a: int, b: int, process: str, title: str, idle: bool = False) -> ActivitySpan:
    return ActivitySpan(start_ms=a, end_ms=b, process=process, title=title, idle=idle)


def _work_span(block: Block, a: int, b: int) -> ActivitySpan:
    m = block.work_matchers[0]
    if m.field == "process":
        return _span(a, b, m.pattern, "documento de trabajo")
    return _span(a, b, "notepad.exe", f"{m.pattern} - trabajo")


def basic_synth_day(day: date, blocks: list[Block], profile: str, rng: Random,
                    latency_scale: dict[str, float] | None = None) -> list[ActivitySpan]:
    scale = latency_scale or {}
    out: list[ActivitySpan] = []
    for b in sorted(blocks, key=lambda x: x.planned_start_ms):
        P = b.planned_start_ms
        morning = datetime.fromtimestamp(P / 1000).hour < 12
        if rng.random() < 0.05:
            continue                                                   # compu apagada: device_off
        censored = morning and rng.random() < 0.10
        median_min = 25 if morning else 8
        lat_min = math.exp(rng.gauss(math.log(median_min), 0.6)) * scale.get(b.block_id, 1.0)
        lat = int(min(lat_min, 95 if censored else 88) * MIN) if not censored else 100 * MIN
        t = P
        distracted_first = rng.random() < (0.8 if morning else 0.3)
        while t < P + min(lat, 100 * MIN):
            seg = min(int(rng.uniform(2, 9) * MIN), P + lat - t)
            if seg <= 0:
                break
            if distracted_first or rng.random() < 0.5:
                out.append(_span(t, t + seg, "WhatsApp.exe" if rng.random() < 0.5 else "chrome.exe",
                                 "WhatsApp" if rng.random() < 0.5 else "YouTube - Google Chrome"))
            else:
                out.append(_span(t, t + seg, "explorer.exe", "Carpeta"))
            distracted_first = False
            t += seg
        if not censored:
            out.append(_work_span(b, t, t + 20 * MIN))
    return out
