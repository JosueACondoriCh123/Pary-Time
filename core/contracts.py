"""Contratos congelados de la Fase 0. Fuente única de verdad.

`tools/export_contracts.py` genera desde acá `contracts/schemas/*.json` y `contracts/openapi.json`,
y `tests/integration/test_contracts.py` falla si quedan desincronizados. El Frente D genera sus
tipos TypeScript desde esos JSON Schema, nunca a mano.

Cambiar este archivo después de la Fase 0 es un pedido de contrato: se escribe en el archivo de
coordinación propio (`docs/coordinacion/frente-X.md`) y lo aplica solo el Frente 0.

Convenciones:
  * Tiempos: epoch en milisegundos UTC (`*_ms`, int). Fechas locales: "YYYY-MM-DD".
  * Nada que salga de la compu ni que vaya al journal lleva títulos de ventana, rutas o textos
    escritos por el usuario. Esos campos están marcados LOCAL y viven solo en el SQLite local.
"""
from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACTS_VERSION = "contracts@1"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- enums

class Arm(str, Enum):
    """Condición de un bloque. `control` = sin intervención."""
    control = "control"
    abrir_trabajo = "abrir_trabajo"
    primer_paso = "primer_paso"
    retrasar_distracciones = "retrasar_distracciones"
    cuenta_regresiva = "cuenta_regresiva"


INTERVENTIONS: tuple[Arm, ...] = (Arm.abrir_trabajo, Arm.primer_paso,
                                  Arm.retrasar_distracciones, Arm.cuenta_regresiva)


class TaskKind(str, Enum):
    escritura = "escritura"
    lectura = "lectura"
    estudio = "estudio"
    programacion = "programacion"
    admin = "admin"
    otro = "otro"


class BlockStatus(str, Enum):
    planned = "planned"          # creado, todavía editable
    confirmed = "confirmed"      # confirmado: ya tiene condición sorteada y sellada
    running = "running"          # llegó la hora, se espera el arranque
    started = "started"          # hubo un tramo de trabajo válido
    censored = "censored"        # 90 min sin arrancar
    device_off = "device_off"    # la compu no estuvo prendida en toda la ventana: se excluye
    cancelled = "cancelled"      # cancelado ANTES de confirmar (después de confirmar se aborta)


FINAL_STATUSES = frozenset({BlockStatus.started, BlockStatus.censored, BlockStatus.device_off})


class Category(str, Enum):
    work = "work"
    distraction = "distraction"
    other = "other"
    none = "none"


class TimeOfDay(str, Enum):
    morning = "morning"      # [05:00, 12:00) local
    afternoon = "afternoon"  # [12:00, 18:00)
    evening = "evening"      # [18:00, 05:00)


# ---------------------------------------------------------------- reglas fijas (versionadas)

class OutcomeRules(_Model):
    """Reglas de la métrica primaria. Se citan por `rules_version` en cada outcome y preregistro.
    Cambiarlas es un contrato nuevo (`outcome@2`), nunca una edición silenciosa."""
    rules_version: Literal["outcome@1"] = "outcome@1"
    work_run_s: int = 900          # tramo de trabajo válido: 15 min
    gap_tolerance_s: int = 60      # huecos (otra app, inactivo) más cortos no cortan el tramo
    idle_max_s: int = 120          # sin input hasta 2 min dentro de la app de trabajo sigue contando (leer)
    censor_s: int = 5400           # 90 min sin arrancar = censurado


OUTCOME_RULES = OutcomeRules()


# ---------------------------------------------------------------- bloques (Frente B es dueño)

class Target(_Model):
    """LOCAL. Qué abre la intervención `abrir_trabajo`."""
    kind: Literal["file", "app", "url", "none"]
    value: str = Field("", max_length=1024)


class WorkMatcher(_Model):
    """LOCAL. Una ventana cuenta como trabajo si CUALQUIER matcher coincide
    (subcadena, sin distinguir mayúsculas)."""
    field: Literal["process", "title"]
    pattern: str = Field(min_length=1, max_length=200)


class BlockCreate(_Model):
    local_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    planned_start_ms: int
    planned_minutes: int = Field(ge=15, le=240)
    task_kind: TaskKind
    task_label: str = Field(max_length=120, description="LOCAL. Nunca va al journal.")
    target: Target
    work_matchers: list[WorkMatcher] = Field(min_length=1)


class BlockUpdate(_Model):
    """Solo mientras el bloque está `planned`."""
    planned_start_ms: int | None = None
    planned_minutes: int | None = Field(None, ge=15, le=240)
    task_kind: TaskKind | None = None
    task_label: str | None = Field(None, max_length=120)
    target: Target | None = None
    work_matchers: list[WorkMatcher] | None = None


class Block(BlockCreate):
    """Bloque completo, tal como lo guarda el runtime (LOCAL)."""
    block_id: str = Field(pattern=r"^blk_[0-9a-f]{12}$")
    status: BlockStatus
    created_ms: int
    first_step: str | None = Field(None, max_length=200, description="LOCAL.")
    aborted: bool = False


class BlockView(Block):
    """Lo que la API le muestra a la app. La condición se oculta hasta la hora del bloque."""
    arm_revealed: Arm | None = Field(None, description="null hasta planned_start_ms (salvo primer_paso)")
    needs_first_step: bool = Field(False, description="true si le tocó primer_paso y falta escribirlo")
    experiment_id: str | None = None


class ConfirmDay(_Model):
    local_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class FirstStep(_Model):
    text: str = Field(min_length=1, max_length=200)


# ---------------------------------------------------------------- sensor (Frente A es dueño)

class ActivitySpan(_Model):
    """LOCAL. Tramo continuo con la misma ventana en primer plano y el mismo estado de input.
    Los huecos sin tramos significan compu apagada o suspendida."""
    start_ms: int
    end_ms: int
    process: str = Field(max_length=260)
    title: str = Field(max_length=512)
    idle: bool = Field(description="sin input por más de OutcomeRules.idle_max_s")
    locked: bool = False


class OutcomeFeatures(_Model):
    """Variables derivadas por bloque para el snapshot del consejo. Sin títulos."""
    pre_start_switches: int = Field(ge=0, description="cambios de proceso en primer plano antes del arranque/censura")
    first_category: Category = Field(description="categoría de la primera ventana tras planned_start")
    distraction_s_before_start: int = Field(ge=0)
    sensor_coverage: float = Field(ge=0, le=1, description="fracción de la ventana con muestras del sensor")
    started_early: bool = Field(description="ya estaba trabajando a la hora planeada (latencia recortada a 0)")


class BlockOutcome(_Model):
    """Resultado de un bloque. Lo calcula `core.sensing.outcome.evaluate_block` (Frente A);
    el runtime (Frente B) lo escribe al journal como evento `outcome` cuando es final."""
    block_id: str
    status: Literal["pending", "started", "censored", "device_off"]
    latency_s: float | None = Field(None, description="observada; null si pending/censored/device_off")
    censored: bool
    work_run_start_ms: int | None = None
    features: OutcomeFeatures | None = None
    rules_version: Literal["outcome@1"] = "outcome@1"
    computed_ms: int


class ActivitySummary(_Model):
    """Resumen del día para la app. Sin títulos. Claves de minutes_by_category: "distraction",
    "other", "idle" (sin bloque no se sabe qué es trabajo) y "paused"."""
    local_date: str
    minutes_by_category: dict[str, int]
    sensor_running: bool
    paused_until_ms: int | None = None


# ---------------------------------------------------------------- aleatorización (Frente B)

RANDOMIZATION_SCHEME = "permuted_blocks_4@1"


def permuted_arm(seed_hex: str, experiment_id: str, index: int, treatment: Arm) -> Arm:
    """Referencia normativa del sorteo. Frente B la usa tal cual; Frente C la usa para verificar.

    Bloques permutados de 4 (2 control + 2 tratamiento). Para el bloque de sorteo j = index // 4,
    los cuatro lugares se ordenan por sha256(seed || f"{experiment_id}:{j}:{slot}") y la posición
    index % 4 da la condición. Determinista, sin depender del RNG de ningún lenguaje."""
    j, pos = divmod(index, 4)
    seed = bytes.fromhex(seed_hex)
    slots = [Arm.control, Arm.control, treatment, treatment]
    order = sorted(range(4), key=lambda s: hashlib.sha256(seed + f"{experiment_id}:{j}:{s}".encode()).hexdigest())
    return slots[order[pos]]


def seed_commitment(seed_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(seed_hex)).hexdigest()


class Assignment(_Model):
    block_id: str
    experiment_id: str | None = Field(None, description="null = línea base (siempre control)")
    arm: Arm
    draw_index: int | None = Field(None, ge=0, description="posición en la secuencia sorteada")
    assigned_ms: int


class InterventionEvent(_Model):
    """Evento `intervention` del journal. Los hwnd y nombres de ventana quedan en el estado
    local del runtime, no acá."""
    block_id: str
    arm: Arm
    action: Literal["applied", "reapplied", "reverted", "failed"]
    reason: Literal["block_start", "device_wake", "work_run_reached", "censor",
                    "abort", "emergency_release", "recovery", "error"]
    n_windows: int = Field(0, ge=0)
    ts_ms: int


class OverlayState(_Model):
    """Lo que la app dibuja en el overlay. La app lo consulta cada ~1 s."""
    visible: bool
    kind: Literal["countdown", "first_step"] | None = None
    block_id: str | None = None
    task_label: str | None = None
    planned_start_ms: int | None = None
    text: str | None = None


class RuntimeStatus(_Model):
    active_block_id: str | None
    active_arm_revealed: Arm | None
    interventions_applied: list[Arm]
    next_block_start_ms: int | None
    emergency_released: bool = False


# ---------------------------------------------------------------- consejo (Frente C)

class Moderator(_Model):
    kind: Literal["time_of_day", "task_kind"]
    value: str = Field(description="TimeOfDay o TaskKind según kind")


class Hypothesis(_Model):
    intervention: Arm
    moderator: Moderator | None = None
    expected_ratio: float = Field(gt=0, le=1.5, description="latencia tratamiento / control esperada")
    rationale: str = Field(max_length=600)
    cited_block_ids: list[str] = Field(default_factory=list)


class ToolVerdict(_Model):
    name: Literal["power", "confounders", "multiplicity", "verifier", "constitution"]
    passed: bool
    detail: str = Field(max_length=400)


class RedTeamReport(_Model):
    verdict: Literal["pass", "veto"]
    tools: list[ToolVerdict]
    premortem: str = Field("", max_length=1200, description="del LLM; sin poder de veto")


class Preregistration(_Model):
    """Evento `preregistration`. Se escribe ANTES del primer sorteo del experimento."""
    experiment_id: str = Field(pattern=r"^exp_[0-9a-f]{12}$")
    created_ms: int
    hypothesis: Hypothesis
    arms: tuple[Arm, Arm] = Field(description="(control, tratamiento)")
    primary_metric: Literal["latency_median_censored"] = "latency_median_censored"
    outcome_rules: OutcomeRules
    test: Literal["permutation_median_diff_one_sided@1"] = "permutation_median_diff_one_sided@1"
    n_per_arm: int = Field(ge=4)
    alpha: float = Field(gt=0, lt=0.5)
    seed_commitment: str = Field(pattern=r"^[0-9a-f]{64}$")
    randomization: Literal["permuted_blocks_4@1"] = "permuted_blocks_4@1"
    source: Literal["scout", "allocator_fallback", "exploration_vetoed"]
    red_team: RedTeamReport
    limitations: list[str] = Field(default_factory=list)
    council_version: str


class Resolution(_Model):
    """Evento `resolution`. Revela la semilla: sha256(seed) debe igualar el compromiso."""
    experiment_id: str
    resolved_ms: int
    verdict: Literal["supported", "not_supported", "insufficient"]
    n_control: int
    n_treatment: int
    median_control_s: float | None
    median_treatment_s: float | None
    ratio: float | None
    p_value: float | None
    alpha: float
    censored_control: int
    censored_treatment: int
    excluded_device_off: int
    aborted_blocks: int
    seed_revealed: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProposalRecord(_Model):
    hypothesis: Hypothesis
    source: Literal["scout", "allocator_fallback"]
    red_team: RedTeamReport


class CouncilRun(_Model):
    """Evento `council_run`: todo lo que el consejo miró, incluido lo que vetó."""
    run_id: str = Field(pattern=r"^run_[0-9a-f]{12}$")
    ran_ms: int
    snapshot_sha256: str
    n_blocks_in_snapshot: int
    proposals: list[ProposalRecord]
    chosen_experiment_id: str | None
    llm_used: bool
    fallback_reason: str | None = None
    models: dict[str, str] = Field(default_factory=dict, description='{"scout": "...", "red_team": "..."}')


class ExperimentProgress(_Model):
    """Vista del experimento en curso. NO incluye el efecto hasta llegar al N (anti-espiar)."""
    experiment_id: str
    intervention: Arm
    moderator: Moderator | None
    n_per_arm: int
    n_control_done: int
    n_treatment_done: int
    status: Literal["running", "closed"]
    created_ms: int


class ExperimentRecord(_Model):
    preregistration: Preregistration
    resolution: Resolution | None


class LedgerEntry(_Model):
    intervention: Arm
    alpha: float = Field(gt=0, description="posterior Beta: 1 + apoyados")
    beta: float = Field(gt=0, description="posterior Beta: 1 + no apoyados")
    n_resolved: int
    n_supported: int


class VetoRegret(_Model):
    n_explored: int
    n_replicated: int
    items: list[ExperimentRecord]


class JournalVerify(_Model):
    ok: bool
    n_events: int
    error: str | None = None


class Report(_Model):
    """Reporte exportable (compartible con un profesional). Sin títulos ni textos del usuario."""
    generated_ms: int
    journal: JournalVerify
    experiments: list[ExperimentRecord]
    ledger: list[LedgerEntry]
    veto_regret: VetoRegret
    disclaimer: str = ("Ajustes de flujo de trabajo medidos sobre una sola persona. "
                       "No es tratamiento ni consejo médico.")


# ---------------------------------------------------------------- configuración (Frente 0)

class Settings(_Model):
    distraction_processes: list[str] = ["WhatsApp.exe", "Discord.exe", "Telegram.exe", "Steam.exe"]
    distraction_title_patterns: list[str] = ["youtube", "netflix", "tiktok", "instagram", "facebook",
                                             "twitter", "x.com", "reddit", "twitch"]
    browser_processes: list[str] = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"]
    whitelist_processes: list[str] = []
    raw_retention_days: int = Field(14, ge=1, le=365)
    high_friction_max_fraction: float = Field(0.5, gt=0, le=1)
    exploration_fraction: float = Field(0.10, ge=0, le=0.5)
    family_alpha: float = Field(0.05, gt=0, lt=0.5)
    ollama_base_url: str = "http://localhost:11434/v1"
    scout_model: str = ""
    red_team_model: str = ""


class Health(_Model):
    ok: bool
    version: str
    contracts: str
    journal_seq: int


# ---------------------------------------------------------------- journal

JournalKind = Literal[
    "app_start",          # Frente 0
    "settings_changed",   # Frente 0
    "block_confirmed",    # Frente B
    "assignment",         # Frente B
    "intervention",       # Frente B
    "block_abort",        # Frente B
    "outcome",            # Frente B escribe, Frente A calcula
    "council_run",        # Frente C
    "preregistration",    # Frente C
    "resolution",         # Frente C
]


class BlockConfirmed(_Model):
    """Evento `block_confirmed`: lo mínimo y sin textos del usuario."""
    block_id: str
    local_date: str
    planned_start_ms: int
    planned_minutes: int
    task_kind: TaskKind


class BlockAbort(_Model):
    block_id: str
    ts_ms: int


# Modelos que se exportan a contracts/schemas/.
EXPORTED: dict[str, type[BaseModel]] = {m.__name__: m for m in (
    Target, WorkMatcher, BlockCreate, BlockUpdate, Block, BlockView, ConfirmDay, FirstStep,
    ActivitySpan, OutcomeFeatures, BlockOutcome, ActivitySummary, OutcomeRules,
    Assignment, InterventionEvent, OverlayState, RuntimeStatus,
    Moderator, Hypothesis, ToolVerdict, RedTeamReport, Preregistration, Resolution,
    ProposalRecord, CouncilRun, ExperimentProgress, ExperimentRecord, LedgerEntry, VetoRegret,
    JournalVerify, Report, Settings, Health, BlockConfirmed, BlockAbort,
)}

# Payload de cada tipo de evento del journal.
JOURNAL_PAYLOADS: dict[str, type[BaseModel] | None] = {
    "app_start": None, "settings_changed": None,
    "block_confirmed": BlockConfirmed, "assignment": Assignment, "intervention": InterventionEvent,
    "block_abort": BlockAbort, "outcome": BlockOutcome, "council_run": CouncilRun,
    "preregistration": Preregistration, "resolution": Resolution,
}

