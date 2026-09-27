"""Red Team: herramientas deterministas con poder de veto + pre-mortem del LLM sin poder de veto.

El modelo no puede aprobar lo que las herramientas rechazan (regla heredada de Night Council).

Herramientas:
  * verifier      — cifras y citas (core.council.verifier)
  * power         — N por brazo con la variabilidad de la línea base, inflado por la fracción censurada
                    (la mediana pierde potencia con empates), y que entre en `MAX_WEEKS` de bloques elegibles
  * confounders   — el moderador no puede coincidir con un único día de semana ni con un único tipo de tarea
  * multiplicity  — alpha-investing: el α disponible tiene que ser viable
  * constitution  — un experimento a la vez; tope de alta fricción
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import date

from core.contracts import Arm, Hypothesis, RedTeamReport, Settings, ToolVerdict
from core.council.journal_view import JournalView
from core.council.snapshot import Snapshot
from core.council.verifier import verify
from core.interfaces import moderator_matches
from core.stats.multiplicity import MIN_VIABLE_ALPHA, next_alpha
from core.stats.power import feasibility, mde_ratio, sigma_log

MIN_BASELINE_BLOCKS = 6
MAX_WEEKS = 3.0
MAX_CENSORED_FRACTION = 0.8
CONFOUND_SHARE = 0.7          # si ≥70% de los bloques del moderador caen en un mismo día/tipo, está confundido
WINDOW_DAYS = 28
HIGH_FRICTION = {Arm.retrasar_distracciones}
FALLBACK_MIN_RATIO = 0.3     # pedir más del 70% de reducción ya no es una hipótesis razonable


@dataclass(frozen=True)
class Plan:
    """Lo que el Red Team deja calculado para el preregistro si la hipótesis pasa."""
    n_per_arm: int
    alpha: float
    weeks_needed: float


def _matching_rows(snapshot: Snapshot, h: Hypothesis) -> list[dict]:
    if h.moderator is None:
        return list(snapshot.rows)
    field = "time_of_day" if h.moderator.kind == "time_of_day" else "task_kind"
    return [r for r in snapshot.rows if r[field] == h.moderator.value]


def eligible_blocks_per_week(view: JournalView, moderator) -> float:
    """Ritmo real de bloques confirmados que cumplirían el moderador, en las últimas 4 semanas."""
    blocks = sorted(view.blocks.values(), key=lambda b: b.local_date)
    if not blocks:
        return 0.0
    last = date.fromisoformat(blocks[-1].local_date)
    recent = [b for b in blocks if (last - date.fromisoformat(b.local_date)).days < WINDOW_DAYS]
    span_days = (last - date.fromisoformat(recent[0].local_date)).days + 1
    matching = [b for b in recent if moderator_matches(moderator, b)]
    return len(matching) / max(span_days / 7, 1.0)


def power_tool(h: Hypothesis, snapshot: Snapshot, view: JournalView, alpha: float) -> tuple[ToolVerdict, Plan | None]:
    rows = _matching_rows(snapshot, h)
    if len(rows) < MIN_BASELINE_BLOCKS:
        return ToolVerdict(name="power", passed=False,
                           detail=f"línea base insuficiente: {len(rows)} bloques < {MIN_BASELINE_BLOCKS}"), None
    if not 0 < h.expected_ratio < 1:
        return ToolVerdict(name="power", passed=False, detail="expected_ratio debe ser < 1"), None
    sigma = sigma_log([r["latency_min"] * 60 for r in rows])
    cens = min(sum(r["censored"] for r in rows) / len(rows), MAX_CENSORED_FRACTION)
    per_week = eligible_blocks_per_week(view, h.moderator)
    f = feasibility(sigma, h.expected_ratio, alpha, per_week, max_weeks=math.inf)
    n = math.ceil(f.n_per_arm / (1 - cens))
    weeks = 2 * n / per_week if per_week else math.inf
    ok = weeks <= MAX_WEEKS
    detail = (f"N={n} por brazo (σ_log={sigma:.2f}, censurados {cens:.0%}, ratio {h.expected_ratio:.2f}, "
              f"α={alpha:.4f}); {per_week:.1f} bloques elegibles/semana → {weeks:.1f} semanas"
              + ("" if ok else f" > tope de {MAX_WEEKS:g}"))
    return ToolVerdict(name="power", passed=ok, detail=detail[:400]), Plan(n, alpha, weeks)   # plan aunque vete: la exploración lo usa


def fallback_ratio(snapshot: Snapshot, view: JournalView, alpha: float) -> float | None:
    """Ratio del respaldo: el efecto mínimo detectable sin moderador dentro de MAX_WEEKS (con 5% de margen
    por redondeo). None si no hay línea base o ni un efecto enorme entra."""
    rows = snapshot.rows
    if len(rows) < MIN_BASELINE_BLOCKS:
        return None
    sigma = sigma_log([r["latency_min"] * 60 for r in rows])
    cens = min(sum(r["censored"] for r in rows) / len(rows), MAX_CENSORED_FRACTION)
    budget = math.floor(MAX_WEEKS * eligible_blocks_per_week(view, None) / 2) * (1 - cens) * 0.95
    r = round(mde_ratio(sigma, alpha, budget), 2) if budget >= 4 else 0.0
    return r if FALLBACK_MIN_RATIO <= r < 1 else None


def confounders_tool(h: Hypothesis, snapshot: Snapshot) -> ToolVerdict:
    if h.moderator is None:
        return ToolVerdict(name="confounders", passed=True, detail="sin moderador")
    rows = _matching_rows(snapshot, h)
    if not rows:
        return ToolVerdict(name="confounders", passed=False, detail="el moderador no tiene bloques en la línea base")
    other = "task_kind" if h.moderator.kind == "time_of_day" else "time_of_day"
    for field in ("weekday", other):
        value, count = Counter(r[field] for r in rows).most_common(1)[0]
        share = count / len(rows)
        if share >= CONFOUND_SHARE and len(rows) >= 3:
            return ToolVerdict(name="confounders", passed=False,
                               detail=f"{h.moderator.value} coincide con {field}={value} en {share:.0%} de los bloques")
    return ToolVerdict(name="confounders", passed=True,
                       detail=f"{h.moderator.value} no se concentra en un día ni en un {other}")


def multiplicity_tool(view: JournalView, settings: Settings) -> tuple[ToolVerdict, float]:
    hist = view.alpha_history()
    a = next_alpha(hist, settings.family_alpha)
    ok = a >= MIN_VIABLE_ALPHA
    return ToolVerdict(name="multiplicity", passed=ok,
                       detail=f"hipótesis #{len(hist) + 1} de la familia: α={a:.4f} (alpha-investing)"
                              + ("" if ok else " < mínimo viable")), a


def constitution_tool(h: Hypothesis, view: JournalView, settings: Settings) -> ToolVerdict:
    if view.active_prereg() is not None:
        return ToolVerdict(name="constitution", passed=False, detail="ya hay un experimento en curso")
    if h.intervention == Arm.control:
        return ToolVerdict(name="constitution", passed=False, detail="control no es una intervención")
    if h.intervention in HIGH_FRICTION and settings.high_friction_max_fraction < 0.5:
        return ToolVerdict(name="constitution", passed=False,
                           detail=f"alta fricción en 50% de bloques elegibles > tope {settings.high_friction_max_fraction:.0%}")
    return ToolVerdict(name="constitution", passed=True, detail="un experimento a la vez; fricción dentro del tope")


WEAK_EVIDENCE_TOOLS = frozenset({"power", "confounders"})


def run_tools(h: Hypothesis, snapshot: Snapshot, view: JournalView, settings: Settings,
              check_citations: bool = True) -> tuple[list[ToolVerdict], Plan | None]:
    mult, alpha = multiplicity_tool(view, settings)
    ver = verify(h, snapshot) if check_citations else ToolVerdict(
        name="verifier", passed=True, detail="respaldo determinista: sin cifras ni citas que verificar")
    pw, plan = power_tool(h, snapshot, view, alpha)
    return [ver, pw, confounders_tool(h, snapshot), mult, constitution_tool(h, view, settings)], plan


def report(tools: list[ToolVerdict], premortem: str) -> RedTeamReport:
    return RedTeamReport(verdict="pass" if all(t.passed for t in tools) else "veto", tools=tools,
                         premortem=premortem[:1200])


def vetoed_only_for_weak_evidence(r: RedTeamReport) -> bool:
    failed = {t.name for t in r.tools if not t.passed}
    return bool(failed) and failed <= WEAK_EVIDENCE_TOOLS
