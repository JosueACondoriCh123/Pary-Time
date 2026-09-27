"""Ledger bayesiano: Beta(1 + apoyados, 1 + no apoyados) por intervención.

Solo cuentan veredictos `supported` / `not_supported`; `insufficient` no informa sobre la intervención.
El Allocator usa la media posterior como prior de que "este tipo de intervención funciona en vos".
"""
from __future__ import annotations

from typing import Iterable

from core.contracts import INTERVENTIONS, Arm, LedgerEntry


def build_ledger(results: Iterable[tuple[Arm, str]]) -> list[LedgerEntry]:
    counts = {a: [0, 0] for a in INTERVENTIONS}
    for arm, verdict in results:
        if arm not in counts or verdict not in ("supported", "not_supported"):
            continue
        counts[arm][0 if verdict == "supported" else 1] += 1
    return [LedgerEntry(intervention=a, alpha=1 + s, beta=1 + f, n_resolved=s + f, n_supported=s)
            for a, (s, f) in counts.items()]


def posterior_mean(entry: LedgerEntry) -> float:
    return entry.alpha / (entry.alpha + entry.beta)
