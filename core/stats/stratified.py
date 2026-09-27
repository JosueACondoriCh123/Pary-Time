"""Test preregistrado `permutation_meanlog_diff_stratified@2` (reemplaza a @1 en los preregistros nuevos).

Por qué existe: la simulación acelerada (core/simulate, 2026-09-27) mostró que con bloques de mañana (lentos) y de
tarde (rápidos) la latencia es bimodal, y la mediana agrupada de @1 cae en el hueco entre los dos grupos. Con un
efecto verdadero de ×0.5 dentro de cada franja, @1 midió ratio 0.88 y p = 0.27.

  * y = log(latencia_s + OFFSET_S), censurados = log(censor_s + OFFSET_S)
  * estadístico: promedio PONDERADO de las diferencias dentro de cada estrato (franja horaria),
    Σ_s w_s·(media_c,s − media_t,s) / Σ_s w_s con w_s = n_c,s·n_t,s / (n_c,s + n_t,s) (pesos tipo Mantel-Haenszel).
    Grande favorece H1 (con tratamiento se arranca antes). Estratos con un solo brazo pesan 0.
  * permutaciones DENTRO de cada estrato (los n por estrato y brazo, y por lo tanto los pesos, no cambian)
  * Monte Carlo con semilla fija; p = (1 + #{T ≥ t_obs}) / (1 + B)

Corrección del mismo día, antes de cualquier uso real: la primera versión de @2 comparaba medias AGRUPADAS. Como los
bloques alternan mañana/tarde y el sorteo es en bloques permutados de 4, las condiciones pueden quedar desbalanceadas
por franja (14 mañanas tratadas contra 8 de control), y la media agrupada mezclaba franja con efecto: con ×0.5 real
midió ratio 0.92. El promedio dentro de estratos no se contamina con ese desbalance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from core.stats.power import OFFSET_S

TEST_ID = "permutation_meanlog_diff_stratified@2"
_EPS = 1e-12


@dataclass(frozen=True)
class StratifiedResult:
    statistic: float       # diferencia ponderada de medias de log-latencia (control − tratamiento)
    ratio: float           # exp(−statistic): latencia del tratamiento / control (media geométrica, dentro de franja)
    p_value: float
    n_control: int
    n_treatment: int
    n_resamples: int


def log_values(latency_s: Sequence[float]) -> np.ndarray:
    return np.log(np.asarray(latency_s, dtype=float) + OFFSET_S)


def _weighted_diff(y: np.ndarray, is_c: np.ndarray, strata_idx: list[np.ndarray]) -> np.ndarray:
    """Estadístico para una o muchas asignaciones (`is_c` de forma (n,) o (B, n))."""
    is_c = np.atleast_2d(is_c)
    num = np.zeros(is_c.shape[0])
    den = 0.0
    for idx in strata_idx:
        c = is_c[:, idx]
        n_c = c[0].sum()
        n_t = len(idx) - n_c
        if n_c == 0 or n_t == 0:
            continue
        w = n_c * n_t / (n_c + n_t)
        ys = y[idx]
        sum_c = (c * ys).sum(axis=1)
        num += w * (sum_c / n_c - (ys.sum() - sum_c) / n_t)
        den += w
    return num / den if den else np.zeros(is_c.shape[0])


def stratified_test(control: Sequence[float], control_strata: Sequence[str], treatment: Sequence[float],
                    treatment_strata: Sequence[str], *, n_resamples: int = 20_000, seed: int = 0) -> StratifiedResult:
    """`control` y `treatment` son latencias en segundos (censurados ya valen censor_s)."""
    if not len(control) or not len(treatment):
        raise ValueError("cada brazo necesita al menos una observación")
    y = np.concatenate([log_values(control), log_values(treatment)])
    is_c = np.concatenate([np.ones(len(control), bool), np.zeros(len(treatment), bool)])
    strata = np.asarray(list(control_strata) + list(treatment_strata))
    strata_idx = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    t_obs = float(_weighted_diff(y, is_c, strata_idx)[0])

    rng = np.random.default_rng(seed)
    perm = np.tile(is_c, (n_resamples, 1))
    for idx in strata_idx:
        if len(idx) > 1:
            perm[:, idx] = rng.permuted(perm[:, idx], axis=1)
    stats = _weighted_diff(y, perm, strata_idx)
    hits = int(np.count_nonzero(stats >= t_obs - _EPS))
    return StratifiedResult(t_obs, float(np.exp(-t_obs)), (1 + hits) / (1 + n_resamples), int(is_c.sum()),
                            int((~is_c).sum()), n_resamples)


def sigma_within(latency_s: Sequence[float], strata: Sequence[str]) -> float:
    """Desvío de log-latencia DENTRO de los estratos (residuos respecto de la media de cada estrato)."""
    y = log_values(latency_s)
    s = np.asarray(list(strata))
    if len(y) < 2:
        raise ValueError("hacen falta al menos 2 bloques para estimar la variabilidad")
    resid = np.empty_like(y)
    for g in np.unique(s):
        m = s == g
        resid[m] = y[m] - y[m].mean()
    dof = len(y) - len(np.unique(s))
    return float(np.sqrt((resid ** 2).sum() / max(dof, 1)))
