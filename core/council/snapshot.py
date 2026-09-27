"""Snapshot agregado: lo único que ve el LLM. Sin títulos, sin rutas, sin textos del usuario.

Filas = bloques con outcome final. `facts` = números derivados que el Scout puede citar; el verificador
solo acepta cifras que estén en las filas, en `facts` o en la propia hipótesis. El snapshot se congela con
sha256 de su JSON canónico, que queda en el `council_run`.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import median

from core.contracts import OUTCOME_RULES, Arm
from core.council.journal_view import JournalView
from core.interfaces import time_of_day
from core.journal.canon import canonical, sha256

WEEKDAYS = ("lun", "mar", "mie", "jue", "vie", "sab", "dom")


@dataclass(frozen=True)
class Snapshot:
    data: dict
    sha256: str

    @property
    def rows(self) -> list[dict]:
        return self.data["blocks"]

    def to_prompt(self) -> str:
        return canonical(self.data)


def _latency_min(o) -> float:
    s = OUTCOME_RULES.censor_s if o.censored else o.latency_s
    return round(s / 60, 1)


def _bucket_facts(rows: list[dict]) -> dict:
    n = len(rows)
    lats = [r["latency_min"] for r in rows]
    cens = sum(r["censored"] for r in rows)
    first_d = sum(r["first_category"] == "distraction" for r in rows)
    return {"n": n, "median_latency_min": round(median(lats), 1) if lats else None,
            "censored": cens, "pct_censored": round(100 * cens / n) if n else None,
            "first_is_distraction": first_d, "pct_first_is_distraction": round(100 * first_d / n) if n else None}


def build_snapshot(view: JournalView, *, only_control: bool = True) -> Snapshot:
    rows = []
    for bid, o in sorted(view.outcomes.items(), key=lambda kv: view.blocks[kv[0]].planned_start_ms
                         if kv[0] in view.blocks else 0):
        b, a = view.blocks.get(bid), view.assignments.get(bid)
        if b is None or o.status == "device_off":
            continue
        arm = a.arm if a else Arm.control
        if only_control and arm != Arm.control:
            continue
        f = o.features
        rows.append({
            "block_id": bid, "local_date": b.local_date,
            "weekday": WEEKDAYS[datetime.fromtimestamp(b.planned_start_ms / 1000).weekday()],
            "time_of_day": time_of_day(b.planned_start_ms).value, "task_kind": b.task_kind.value,
            "arm": arm.value, "latency_min": _latency_min(o), "censored": o.censored,
            "aborted": bid in view.aborted,
            "pre_start_switches": f.pre_start_switches if f else None,
            "first_category": f.first_category.value if f else "none",
            "distraction_min_before_start": round(f.distraction_s_before_start / 60, 1) if f else None,
            "started_early": f.started_early if f else False,
        })
    facts: dict = {"all": _bucket_facts(rows)}
    for key in ("time_of_day", "task_kind", "weekday", "first_category"):
        groups: dict[str, list] = defaultdict(list)
        for r in rows:
            groups[r[key]].append(r)
        facts[f"by_{key}"] = {g: _bucket_facts(rs) for g, rs in sorted(groups.items())}
    dates = sorted({r["local_date"] for r in rows})
    data = {"rules": OUTCOME_RULES.rules_version, "n_blocks": len(rows),
            "first_date": dates[0] if dates else None, "last_date": dates[-1] if dates else None,
            "weekday_counts": dict(Counter(r["weekday"] for r in rows)), "facts": facts, "blocks": rows}
    return Snapshot(data, sha256(canonical(data)))
