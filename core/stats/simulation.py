"""Experimentos SINTÉTICOS para validar la estadística. Nunca se usan como evidencia sobre una persona.

Modelo generador: log(latencia + OFFSET) ~ Normal(μ, σ) en control; en tratamiento la latencia se multiplica
por `ratio`. Se censura en `censor_s`. Es el mismo modelo que supone `power.py`, así que sirve para ver si la
fórmula de N y el test de permutación real cuentan la misma historia.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.contracts import OUTCOME_RULES
from core.stats.permutation import permutation_test
from core.stats.power import OFFSET_S


def draw_latencies(rng: np.random.Generator, n: int, median_s: float, sigma: float, ratio: float = 1.0,
                   censor_s: float = OUTCOME_RULES.censor_s) -> np.ndarray:
    mu = np.log(median_s + OFFSET_S)
    lat = np.exp(rng.normal(mu, sigma, n)) - OFFSET_S
    lat = np.clip(lat, 0, None) * ratio
    return np.minimum(lat, censor_s)          # censurado = censor_s, como en el análisis real


@dataclass(frozen=True)
class SimResult:
    rejection_rate: float
    reps: int


def rejection_rate(*, n_per_arm: int, median_s: float, sigma: float, ratio: float, alpha: float,
                   reps: int = 400, n_resamples: int = 2000, seed: int = 0) -> SimResult:
    rng = np.random.default_rng(seed)
    hits = 0
    for r in range(reps):
        c = draw_latencies(rng, n_per_arm, median_s, sigma)
        t = draw_latencies(rng, n_per_arm, median_s, sigma, ratio)
        if permutation_test(c, t, n_resamples=n_resamples, seed=seed + r, max_exact=0).p_value <= alpha:
            hits += 1
    return SimResult(hits / reps, reps)
