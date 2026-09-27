"""Allocator: elige qué experimento correr entre las hipótesis que sobrevivieron al Red Team.

Puntaje = ganancia esperada × prior del ledger / (fricción × semanas necesarias).
  * ganancia esperada: 1 − expected_ratio (cuánto se acortaría la latencia)
  * prior: media posterior Beta de que ese tipo de intervención funcionó en esta persona
  * fricción: cuánto molesta la intervención (escribir la noche antes, ventanas minimizadas)

Respaldo si el LLM falla o se abstiene: una hipótesis por intervención, sin moderador, con el efecto
mínimo detectable dentro del tope de semanas (diseño estándar cuando no hay hipótesis previa).
Exploración (veto regret): con probabilidad `exploration_fraction`, y si no hay ninguna aprobada o toca
explorar, se elige una vetada SOLO por evidencia débil (potencia o confusores), nunca por la constitución,
el verificador o la multiplicidad.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from core.contracts import INTERVENTIONS, Arm, Hypothesis, LedgerEntry, RedTeamReport
from core.council.red_team import Plan, vetoed_only_for_weak_evidence
from core.stats.ledger import posterior_mean

FRICTION = {Arm.abrir_trabajo: 1.0, Arm.cuenta_regresiva: 1.0, Arm.primer_paso: 2.0,
            Arm.retrasar_distracciones: 3.0}


@dataclass(frozen=True)
class Candidate:
    hypothesis: Hypothesis
    source: str                 # scout | allocator_fallback
    red_team: RedTeamReport
    plan: Plan | None


def fallback_hypotheses(ratio: float) -> list[Hypothesis]:
    """Una por intervención, sin moderador, con el efecto mínimo detectable en el tope de semanas."""
    return [Hypothesis(intervention=a, moderator=None, expected_ratio=ratio,
                       rationale="Respaldo determinista del Allocator: el Scout no propuso hipótesis válidas; "
                                 "se preregistra el efecto mínimo detectable en el tope de semanas.",
                       cited_block_ids=[]) for a in INTERVENTIONS]


def score(c: Candidate, ledger: list[LedgerEntry]) -> float:
    prior = next((posterior_mean(e) for e in ledger if e.intervention == c.hypothesis.intervention), 0.5)
    weeks = c.plan.weeks_needed if c.plan and c.plan.weeks_needed > 0 else 1.0
    return (1 - c.hypothesis.expected_ratio) * prior / (FRICTION[c.hypothesis.intervention] * weeks)


def choose(candidates: list[Candidate], ledger: list[LedgerEntry], exploration_fraction: float,
           rng: random.Random) -> tuple[Candidate | None, str | None]:
    """(elegido, source del preregistro). source ∈ {scout, allocator_fallback, exploration_vetoed}."""
    passed = [c for c in candidates if c.red_team.verdict == "pass" and c.plan is not None]
    explorable = [c for c in candidates if vetoed_only_for_weak_evidence(c.red_team) and c.plan is not None]
    if explorable and rng.random() < exploration_fraction:
        pick = max(explorable, key=lambda c: score(c, ledger))
        return pick, "exploration_vetoed"
    if passed:
        pick = max(passed, key=lambda c: score(c, ledger))
        return pick, pick.source
    return None, None
