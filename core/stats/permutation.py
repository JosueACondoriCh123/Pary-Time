"""Test preregistrado `permutation_median_diff_one_sided@1`.

H0: la condición no cambia la latencia. H1: con tratamiento se arranca antes (latencia menor).
Estadístico: mediana(control) − mediana(tratamiento); valores grandes favorecen H1.

  * Exacto cuando las particiones posibles son ≤ `max_exact` (enumera todas; p = #{T ≥ t_obs} / total).
  * Si no, Monte Carlo con `n_resamples` permutaciones y semilla fija; p = (1 + #{T ≥ t_obs}) / (1 + B),
    que nunca da 0 y es válido (Phipson & Smyth 2010). Misma semilla, mismo p.

Los censurados entran como `censor_s` (el peor valor posible): con la mediana eso es conservador.
Los `device_off` no entran: se excluyen antes de llamar acá.
"""
from __future__ import annotations

import hashlib
import itertools
import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

TEST_ID = "permutation_median_diff_one_sided@1"
_EPS = 1e-9          # tolerancia al comparar estadísticos en punto flotante


@dataclass(frozen=True)
class PermutationResult:
    statistic: float          # mediana(control) − mediana(tratamiento), en segundos
    p_value: float
    n_control: int
    n_treatment: int
    exact: bool
    n_resamples: int          # particiones evaluadas (todas si exact)


def latency_values(latencies: Sequence[float | None], censored: Sequence[bool], censor_s: float) -> np.ndarray:
    """Latencias observadas; los censurados valen `censor_s`."""
    if len(latencies) != len(censored):
        raise ValueError("latencies y censored con largos distintos")
    out = []
    for lat, cen in zip(latencies, censored):
        if cen:
            out.append(float(censor_s))
        elif lat is None:
            raise ValueError("latencia faltante en un bloque no censurado")
        else:
            out.append(min(float(lat), float(censor_s)))
    return np.asarray(out, dtype=float)


def seed_from(label: str) -> int:
    """Semilla reproducible desde un texto (p.ej. el experiment_id)."""
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")


def median_diff(control: np.ndarray, treatment: np.ndarray) -> float:
    return float(np.median(control) - np.median(treatment))


def permutation_test(control: Sequence[float], treatment: Sequence[float], *, n_resamples: int = 20_000,
                     seed: int = 0, max_exact: int = 200_000) -> PermutationResult:
    c = np.asarray(control, dtype=float)
    t = np.asarray(treatment, dtype=float)
    if len(c) == 0 or len(t) == 0:
        raise ValueError("cada brazo necesita al menos una observación")
    pooled = np.concatenate([c, t])
    n, k = len(pooled), len(c)
    t_obs = median_diff(c, t)
    total = math.comb(n, k)

    if total <= max_exact:
        combos = np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(n), k)),
                             dtype=np.int64, count=total * k).reshape(total, k)
        mask = np.zeros((total, n), dtype=bool)
        np.put_along_axis(mask, combos, True, axis=1)
        tiled = np.broadcast_to(pooled, (total, n))
        stats = (np.median(tiled[mask].reshape(total, k), axis=1)
                 - np.median(tiled[~mask].reshape(total, n - k), axis=1))
        hits = int(np.count_nonzero(stats >= t_obs - _EPS))
        return PermutationResult(t_obs, hits / total, k, len(t), True, total)

    rng = np.random.default_rng(seed)
    perms = rng.permuted(np.tile(pooled, (n_resamples, 1)), axis=1)
    stats = np.median(perms[:, :k], axis=1) - np.median(perms[:, k:], axis=1)
    hits = int(np.count_nonzero(stats >= t_obs - _EPS))
    return PermutationResult(t_obs, (1 + hits) / (1 + n_resamples), k, len(t), False, n_resamples)
