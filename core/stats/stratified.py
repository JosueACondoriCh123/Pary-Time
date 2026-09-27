"""Test preregistrado `permutation_meanlog_diff_stratified@2` (reemplaza a @1 en los preregistros nuevos).

Por qué existe: la simulación acelerada (core/simulate, 2026-09-27) mostró que con bloques de mañana (lentos) y de
tarde (rápidos) la latencia es bimodal, y la mediana agrupada de @1 cae en el hueco entre los dos grupos. Con un
efecto verdadero de ×0.5 dentro de cada franja, @1 midió ratio 0.88 y p = 0.27.

  * y = log(latencia_s + OFFSET_S), censurados = log(censor_s + OFFSET_S)
  * estadístico: media(y_control) − media(y_tratamiento); grande favorece H1 (con tratamiento se arranca antes)
  * permutaciones DENTRO de cada estrato (franja horaria): el sorteo real ya es parejo por bloques, y así la
    diferencia mañana/tarde no se mezcla con el efecto
  * Monte Carlo con semilla fija; p = (1 + #{T ≥ t_obs}) / (1 + B)
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
    statistic: float       # diferencia de medias de log-latencia (control − tratamiento)
    ratio: float           # exp(−statistic): latencia del tratamiento / control (media geométrica)
    p_value: float
    n_control: int
    n_treatment: int
    n_resamples: int


def log_values(latency_s: Sequence[float]) -> np.ndarray:
    return np.log(np.asarray(latency_s, dtype=float) + OFFSET_S)


def stratified_test(control: Sequence[float], control_strata: Sequence[str], treatment: Sequence[float],
                    treatment_strata: Sequence[str], *, n_resamples: int = 20_000, seed: int = 0) -> StratifiedResult:
    """`control` y `treatment` son latencias en segundos (censurados ya valen censor_s)."""
    if not len(control) or not len(treatment):
        raise ValueError("cada brazo necesita al menos una observación")
    y = np.concatenate([log_values(control), log_values(treatment)])
    is_c = np.concatenate([np.ones(len(control), bool), np.zeros(len(treatment), bool)])
    strata = np.asarray(list(control_strata) + list(treatment_strata))
    t_obs = float(y[is_c].mean() - y[~is_c].mean())

    rng = np.random.default_rng(seed)
    perm = np.tile(is_c, (n_resamples, 1))
    for s in np.unique(strata):
        idx = np.flatnonzero(strata == s)
        if len(idx) > 1:
            block = perm[:, idx]
            perm[:, idx] = rng.permuted(block, axis=1)
    n_c = is_c.sum()
    sums_c = (perm * y).sum(axis=1)
    stats = sums_c / n_c - (y.sum() - sums_c) / (len(y) - n_c)
    hits = int(np.count_nonzero(stats >= t_obs - _EPS))
    return StratifiedResult(t_obs, float(np.exp(-t_obs)), (1 + hits) / (1 + n_resamples), int(n_c),
                            int(len(y) - n_c), n_resamples)


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
