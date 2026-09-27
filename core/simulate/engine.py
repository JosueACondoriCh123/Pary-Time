"""Simulación acelerada con el código REAL: línea base → consejo → experimento → resolución.

Para la demo de la hackathon y como prueba de ciclo completo. Nada se finge por fuera del contrato:
  * los bloques se crean y se confirman con el `RuntimeService` de B (el sorteo sale de `permuted_arm`);
  * los tramos de actividad son SINTÉTICOS (`synth_day`, Frente A) y se guardan en el `SpanStore` real;
  * el scheduler de B los evalúa con `evaluate_block` de A y escribe los `outcome`;
  * el consejo de C preregistra (con respaldo determinista si no hay LLM) y resuelve con la semilla revelada.
El reloj es manual y el escritorio está apagado (`NDE1_NO_DESKTOP=1`): no se minimiza ni se abre nada real.
El data_dir queda marcado `DATA_LABEL = sintetico`, así la app muestra la franja "DATOS SINTÉTICOS".
"""
from __future__ import annotations

import importlib.util
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from core.app import SettingsStore
from core.contracts import Arm, BlockCreate, Settings, Target, TaskKind, WorkMatcher
from core.council.council import Council, SeedStore
from core.council.journal_view import JournalView
from core.council.experiments import Experiments
from core.interfaces import AppContext, SynthDay
from core.journal import Journal
from core.llm import LLMError, OpenAICompatClient
from core.sensing.categorize import categorize
from core.sensing.outcome import evaluate_block
from core.sensing.store import SpanStore
from core.simulate.basic_synth import basic_synth_day

ROOT = Path(__file__).resolve().parents[2]
MIN = 60_000

# Plan diario de la persona simulada: (hora, minuto, tipo de tarea, etiqueta, matcher de trabajo)
DAILY = [(9, 0, TaskKind.escritura, "Tesis cap. 3", WorkMatcher(field="process", pattern="WINWORD.EXE")),
         (15, 0, TaskKind.lectura, "Leer papers", WorkMatcher(field="process", pattern="AcroRd32.exe"))]


class ManualClock:
    def __init__(self, ms: int):
        self.ms = ms

    def now_ms(self) -> int:
        return self.ms


def load_synth() -> tuple[SynthDay, str]:
    """`tools/capture/synth.py` del Frente A si está; si no, el generador mínimo de respaldo."""
    path = ROOT / "tools" / "capture" / "synth.py"
    if path.exists():
        spec = importlib.util.spec_from_file_location("nde1_synth", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.synth_day, "tools/capture/synth.py"
    return basic_synth_day, "core/simulate/basic_synth.py"


@dataclass
class SimResult:
    out: Path
    days: int
    blocks: int
    experiment_id: str | None
    verdict: str | None
    synth: str


def _ms(d: date, h: int, m: int = 0) -> int:
    return int(datetime(d.year, d.month, d.day, h, m).timestamp() * 1000)


def simulate(out: Path, *, weeks: int = 5, seed: int = 7, true_effect: float = 0.5,
             start: date | None = None, llm: str = "off", cassettes: Path | None = None) -> SimResult:
    """Corre `weeks` semanas simuladas en `out` (que tiene que no existir o estar vacío).

    `true_effect`: factor real sobre la latencia en los bloques con intervención (0.5 = la mitad). Es el efecto
    VERDADERO de la simulación; el consejo no lo conoce y tiene que descubrirlo con el test preregistrado.
    `llm`: `off` (respaldo determinista del Allocator), `cache` o `live` (Ollama, cassettes en `out`)."""
    os.environ["NDE1_NO_DESKTOP"] = "1"
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} no está vacío: la simulación no pisa datos existentes")
    out.mkdir(parents=True, exist_ok=True)
    (out / "DATA_LABEL").write_text("sintetico\n", encoding="utf-8")

    from core.runtime import RuntimeService            # runtime de B, API pública
    from core.runtime.interventions import NoWindows

    rng = random.Random(seed)
    first = start or (date.today() - timedelta(days=7 * weeks + 1))
    clock = ManualClock(_ms(first - timedelta(days=1), 21))
    journal = Journal(out / "journal.jsonl")
    settings_store = SettingsStore(out / "settings.json")
    settings_store.put(Settings())
    spans = SpanStore(out / "activity.sqlite")
    ctx = AppContext(journal=journal, settings=settings_store.get, data_dir=out, activity=spans,
                     evaluate_block=evaluate_block, categorize=categorize)
    seeds = SeedStore(out)

    def factory(role: str, model: str) -> OpenAICompatClient:
        if llm == "off":                                   # el consejo lo toma como LLM caído → respaldo
            raise LLMError("simulación sin LLM (--llm off)")
        return OpenAICompatClient.for_ollama(Settings().ollama_base_url, model, mode=llm,
                                             cassette_dir=Path(cassettes) if cassettes else out / "llm_cassettes",
                                             timeout=600)

    ids = random.Random(seed + 1)
    council = Council(journal, settings_store.get, seeds, factory, now_ms=clock.now_ms,
                      new_id=lambda: f"{ids.getrandbits(48):012x}",
                      new_seed=lambda: f"{ids.getrandbits(256):064x}")   # sorteo reproducible (solo simulación)
    experiments = Experiments(journal, settings_store.get, seeds, now_ms=clock.now_ms)
    ctx.experiments = experiments
    runtime = RuntimeService(ctx, clock, NoWindows())
    runtime.scheduler.opener = lambda value: None          # abrir_trabajo "abre" sin tocar el escritorio
    synth, synth_name = load_synth()

    n_blocks, last_day = 0, first
    for d in range(7 * weeks):
        day = first + timedelta(days=d)
        last_day = day
        # 1. La noche anterior: planear y confirmar (sortea si hay experimento activo).
        clock.ms = _ms(day - timedelta(days=1), 21, 30)
        for h, m, kind, label, matcher in DAILY:
            runtime.create_block(BlockCreate(local_date=day.isoformat(), planned_start_ms=_ms(day, h, m),
                                             planned_minutes=50, task_kind=kind, task_label=label,
                                             target=Target(kind="url", value="https://example.org/trabajo"),
                                             work_matchers=[matcher]))
        views = runtime.confirm_day(day.isoformat())
        for v in views:
            if v.needs_first_step:
                runtime.set_first_step(v.block_id, "Escribir una oración, aunque sea fea")
        # 2. El día: tramos sintéticos con el efecto verdadero en los bloques con intervención.
        records = [runtime.store.get(v.block_id) for v in views]
        scale = {r.block.block_id: (true_effect if r.arm not in (None, Arm.control) else 1.0) for r in records}
        for span in synth(day, [r.block for r in records], "tdah_mananas", rng, scale):
            spans.write(span)
        # 3. El scheduler recorre el día cada 2 minutos: aplica, evalúa, escribe outcomes, resuelve.
        t, end = _ms(day, 8, 55), _ms(day, 23, 0)
        while t <= end:
            clock.ms = t
            runtime.scheduler.tick(t)
            t += 2 * MIN
        n_blocks += len(views)
        # 4. El consejo se reúne una vez por semana (domingo 20:00) si no hay experimento en curso.
        if day.weekday() == 6 or d == 6:
            clock.ms = _ms(day, 20)
            if JournalView.load(journal).active_prereg() is None:
                council.run()
        if JournalView.load(journal).resolutions and d >= 7 * weeks - 1:
            break

    view = JournalView.load(journal)
    exp = view.preregs[0].experiment_id if view.preregs else None
    verdict = view.resolutions[exp].verdict if exp and exp in view.resolutions else None
    runtime.stop()
    spans.close()
    return SimResult(out, (last_day - first).days + 1, n_blocks, exp, verdict, synth_name)
