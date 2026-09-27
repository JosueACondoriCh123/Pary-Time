"""Interfaces Python entre frentes (congeladas en la Fase 0, igual que `core/contracts.py`).

Un frente nunca importa internals de otro: solo lo que está acá. `core/app.py` arma el grafo:

    sensing (A)  ──ActivitySource, evaluate_block, categorize──▶  runtime (B)
    council (C)  ──ExperimentProvider──────────────▶  runtime (B)
    runtime (B)  ──journal: block_confirmed, assignment, intervention, outcome──▶  council (C)

El journal es la fuente de verdad compartida: el consejo lee de ahí outcomes y asignaciones,
nunca del estado interno del runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from random import Random
from typing import Callable, Protocol

from fastapi import APIRouter

from core.contracts import (ActivitySpan, Arm, Block, BlockOutcome, Category, Moderator, Settings,
                            TimeOfDay)
from core.journal import Journal


def time_of_day(ms: int) -> TimeOfDay:
    """Franja horaria LOCAL de la compu para un instante."""
    h = datetime.fromtimestamp(ms / 1000).hour
    if 5 <= h < 12:
        return TimeOfDay.morning
    if 12 <= h < 18:
        return TimeOfDay.afternoon
    return TimeOfDay.evening


def moderator_matches(moderator: Moderator | None, block: Block) -> bool:
    if moderator is None:
        return True
    if moderator.kind == "time_of_day":
        return time_of_day(block.planned_start_ms).value == moderator.value
    return block.task_kind.value == moderator.value


# ------------------------------------------------------------ Frente A → B

class ActivitySource(Protocol):
    """Implementa Frente A (`core.sensing`)."""

    def spans(self, start_ms: int, end_ms: int) -> list[ActivitySpan]:
        """Tramos que se solapan con [start_ms, end_ms), en orden. Huecos = compu apagada."""
        ...

    def last_sample_ms(self) -> int | None:
        """Última muestra del sensor (para saber si está vivo)."""
        ...


# evaluate_block(block, spans, now_ms, settings) -> BlockOutcome. Función PURA (Frente A):
# mismo input, mismo output; sin reloj ni disco. `status="pending"` mientras no sea final.
EvaluateBlock = Callable[[Block, list[ActivitySpan], int, Settings], BlockOutcome]


# categorize(span, block, settings) -> Category. Función PURA (Frente A). Con block=None nunca
# devuelve `work` (sin bloque no se sabe qué es trabajo). El runtime la usa para esconder el overlay
# en cuanto la ventana activa es trabajo.
Categorize = Callable[[ActivitySpan, Block | None, Settings], Category]


# synth_day(day, blocks, profile, rng, latency_scale) -> list[ActivitySpan]. Frente A (`tools/capture/synth.py`), solo para
# DEMO y tests: tramos SINTÉTICOS realistas de un día local `day` alrededor de los `blocks` de ese día, con
# `profile` ("tdah_mananas" por defecto: mañanas que arrancan en distracción, tardes más rápidas, algún
# apagado y alguna pausa) y un `random.Random` sembrado (misma semilla, mismos tramos). Los tramos no se solapan,
# están en orden y usan procesos/títulos genéricos (nunca datos reales). `latency_scale` ({block_id: factor})
# multiplica la latencia de arranque de ese bloque (p.ej. 0.5 = con la intervención arranca en la mitad): así la
# simulación tiene un efecto verdadero conocido. Lo consume `core.simulate` (Frente C).
SynthDay = Callable[[date, list[Block], str, Random, "dict[str, float] | None"], list[ActivitySpan]]


# ------------------------------------------------------------ Frente C → B

@dataclass(frozen=True)
class ActiveExperiment:
    """Experimento en curso. Contiene la semilla: NUNCA se serializa a la API ni al journal
    (en el journal solo va `seed_commitment`, y la semilla se revela en `resolution`)."""
    experiment_id: str
    treatment: Arm
    moderator: Moderator | None
    n_per_arm: int
    seed_hex: str = field(repr=False)

    def eligible(self, block: Block) -> bool:
        return moderator_matches(self.moderator, block)


class ExperimentProvider(Protocol):
    """Implementa Frente C (`core.council`)."""

    def active(self) -> ActiveExperiment | None:
        """None = línea base o sin experimento: el runtime asigna `control` sin experiment_id."""
        ...

    def after_outcome(self, outcome: BlockOutcome) -> None:
        """El runtime lo llama después de escribir cada `outcome` final. El consejo decide si
        el experimento alcanzó su N y, si es así, escribe la `resolution`."""
        ...


# ------------------------------------------------------------ composición

@dataclass
class AppContext:
    journal: Journal
    settings: Callable[[], Settings]
    data_dir: Path
    activity: ActivitySource | None = None
    evaluate_block: EvaluateBlock | None = None
    categorize: Categorize | None = None
    experiments: ExperimentProvider | None = None


class FrontService(Protocol):
    """Lo que devuelve `build(ctx)` de cada paquete de frente."""
    router: APIRouter

    def start(self) -> None: ...

    def stop(self) -> None: ...

