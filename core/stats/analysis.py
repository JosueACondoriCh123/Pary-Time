"""Análisis preregistrado de un experimento: de outcomes finales a los números de la `resolution`.

Intención de tratar: los bloques abortados cuentan en su brazo con lo que haya pasado. `device_off` se
excluye. Los censurados valen `censor_s`. El veredicto es `insufficient` si algún brazo no llegó al N
preregistrado (solo pasa si el experimento se cierra antes de tiempo).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from core.contracts import BlockOutcome, OutcomeRules
from core.stats.permutation import latency_values, permutation_test, seed_from


@dataclass(frozen=True)
class Analysis:
    verdict: str                     # supported | not_supported | insufficient
    n_control: int
    n_treatment: int
    median_control_s: float | None
    median_treatment_s: float | None
    ratio: float | None
    p_value: float | None
    censored_control: int
    censored_treatment: int
    excluded_device_off: int


def _usable(outcomes: Sequence[BlockOutcome]) -> list[BlockOutcome]:
    return [o for o in outcomes if o.status in ("started", "censored")]


def analyze(control: Sequence[BlockOutcome], treatment: Sequence[BlockOutcome], *, n_per_arm: int,
            alpha: float, experiment_id: str, rules: OutcomeRules) -> Analysis:
    excluded = sum(o.status == "device_off" for o in [*control, *treatment])
    c, t = _usable(control), _usable(treatment)
    cen_c, cen_t = sum(o.censored for o in c), sum(o.censored for o in t)
    if len(c) < n_per_arm or len(t) < n_per_arm or not c or not t:
        return Analysis("insufficient", len(c), len(t), None, None, None, None, cen_c, cen_t, excluded)
    vc = latency_values([o.latency_s for o in c], [o.censored for o in c], rules.censor_s)
    vt = latency_values([o.latency_s for o in t], [o.censored for o in t], rules.censor_s)
    res = permutation_test(vc, vt, seed=seed_from(experiment_id))
    mc, mt = float(np.median(vc)), float(np.median(vt))
    ratio = round(mt / mc, 4) if mc > 0 else None
    verdict = "supported" if res.p_value <= alpha else "not_supported"
    return Analysis(verdict, len(c), len(t), mc, mt, ratio, res.p_value, cen_c, cen_t, excluded)
