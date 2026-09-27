"""Potencia y factibilidad: la herramienta `power` del Red Team.

Escala: y = log(latencia_s + OFFSET_S). El desplazamiento evita log(0) cuando se arranca en el acto y achica
el peso de diferencias de segundos. Un efecto `expected_ratio = r` se traduce en δ = −log(r) sobre y
(aproximación: ignora el desplazamiento, así que para latencias chicas sobreestima el efecto; por eso
se exige potencia 0.8 y el test real es de permutación, no este modelo).

N por brazo para un test a una cola sobre medias con desvío σ, dividido por la eficiencia relativa
asintótica de la mediana frente a la media bajo normalidad (2/π): la mediana pide ~57% más datos.
`tests/stats/test_power.py` contrasta esta fórmula contra simulación del test real.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Sequence

import numpy as np

OFFSET_S = 60.0
MEDIAN_ARE = 2 / math.pi
MIN_N_PER_ARM = 4


def log_latency(values: Sequence[float]) -> np.ndarray:
    return np.log(np.asarray(values, dtype=float) + OFFSET_S)


def sigma_log(values: Sequence[float]) -> float:
    """Desvío de log-latencia (muestral, ddof=1). Necesita ≥ 2 valores."""
    y = log_latency(values)
    if len(y) < 2:
        raise ValueError("hacen falta al menos 2 bloques para estimar la variabilidad")
    return float(np.std(y, ddof=1))


def required_n_per_arm(sigma: float, expected_ratio: float, alpha: float, power: float = 0.8,
                       efficiency: float = MEDIAN_ARE) -> int:
    if not 0 < expected_ratio < 1:
        raise ValueError("expected_ratio debe estar en (0, 1): solo se buscan reducciones de latencia")
    if sigma <= 0:
        return MIN_N_PER_ARM
    delta = -math.log(expected_ratio)
    z = NormalDist().inv_cdf
    n_mean = 2 * ((z(1 - alpha) + z(power)) * sigma / delta) ** 2
    return max(MIN_N_PER_ARM, math.ceil(n_mean / efficiency))


def mde_ratio(sigma: float, alpha: float, n_per_arm: float, power: float = 0.8,
              efficiency: float = MEDIAN_ARE) -> float:
    """Efecto mínimo detectable (como ratio de latencias) con `n_per_arm`: inversa de required_n_per_arm."""
    if n_per_arm <= 0:
        return 0.0
    z = NormalDist().inv_cdf
    delta = (z(1 - alpha) + z(power)) * sigma * math.sqrt(2 / (n_per_arm * efficiency))
    return math.exp(-delta)


@dataclass(frozen=True)
class Feasibility:
    n_per_arm: int
    eligible_blocks_per_week: float
    weeks_needed: float
    feasible: bool
    detail: str


def feasibility(sigma: float, expected_ratio: float, alpha: float, eligible_blocks_per_week: float,
                max_weeks: float = 3.0, power: float = 0.8, efficiency: float = MEDIAN_ARE) -> Feasibility:
    n = required_n_per_arm(sigma, expected_ratio, alpha, power, efficiency)
    if eligible_blocks_per_week <= 0:
        return Feasibility(n, 0.0, math.inf, False, "no hay bloques elegibles en la línea base")
    weeks = 2 * n / eligible_blocks_per_week
    ok = weeks <= max_weeks
    detail = (f"N={n} por brazo (σ_log={sigma:.2f}, ratio {expected_ratio:.2f}, α={alpha:.4f}); "
              f"{eligible_blocks_per_week:.1f} bloques elegibles/semana → {weeks:.1f} semanas"
              + ("" if ok else f" > tope de {max_weeks:g}"))
    return Feasibility(n, eligible_blocks_per_week, weeks, ok, detail)
