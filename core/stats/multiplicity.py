"""Comparaciones múltiples: alpha-investing (Foster & Stine, 2008). Herramienta `multiplicity`.

Una persona prueba hipótesis de a una, durante meses. Bonferroni sobre una familia abierta asfixia a
cualquier N-de-1; alpha-investing controla la mFDR secuencial y **premia los hallazgos**:

    W₀ = α_f · (1 − α_f)                     riqueza inicial
    α_k = W / 2                               política: cada test gasta la mitad de la riqueza
    W ← W − α_k / (1 − α_k) + ω · rechazó     con pago ω = α_f

Con W₀ ≤ α_f·η (η = 1 − α_f) y ω ≤ α_f, mFDR_η ≤ α_f. El historial sale de las `resolution` del journal
(alpha usado, veredicto) en orden; los experimentos `insufficient` pagan igual que un no-rechazo.
"""
from __future__ import annotations

from typing import Iterable

MIN_VIABLE_ALPHA = 0.001     # por debajo, ningún N factible alcanza: el Red Team veta


def initial_wealth(family_alpha: float) -> float:
    return family_alpha * (1 - family_alpha)


def wealth_after(history: Iterable[tuple[float, bool]], family_alpha: float) -> float:
    """`history`: (alpha usado, rechazó H0) por cada experimento resuelto, en orden."""
    w = initial_wealth(family_alpha)
    for alpha_k, rejected in history:
        w -= alpha_k / (1 - alpha_k)
        if rejected:
            w += family_alpha
    return max(w, 0.0)


def next_alpha(history: Iterable[tuple[float, bool]], family_alpha: float) -> float:
    return wealth_after(history, family_alpha) / 2
