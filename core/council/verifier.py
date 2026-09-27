"""Verificador: toda cifra de la justificación tiene que estar en el snapshot o en la propia hipótesis.

Mismo espíritu que Night Council: el modelo puede razonar, pero no puede traer números de afuera. Cada cifra se
ata a su UNIDAD, porque en la corrida real (qwen3.5:4b, 2026-09-26) el Scout escribió "50% de escritura
censurados" cuando era 4%, y el 50 pasaba por existir en otro lado del snapshot:
  * `N%`   → tiene que ser un porcentaje del snapshot (`pct_*`) o la lectura en % del `expected_ratio`
  * `N min`→ tiene que ser una latencia o unos minutos del snapshot (`*latency_min`, `*_min_*`)
  * `N`    → cualquier número del snapshot (conteos, etc.)
Y un porcentaje se ata además a su TEMA si la cláusula lo nombra: "censur…" → `pct_censored`, "distrac…" →
`pct_first_is_distraction`. (El 50 del caso real existía, pero como porcentaje de distracción de otro grupo.)
Se ignoran ids de bloque, fechas y horas (no son afirmaciones cuantitativas).
"""
from __future__ import annotations

import re

from core.contracts import Hypothesis, ToolVerdict
from core.council.snapshot import Snapshot

_IGNORE = re.compile(r"blk_[0-9a-f]{12}|\d{4}-\d{2}-\d{2}|\b\d{1,2}:\d{2}\b")
_NUM = re.compile(r"(?<![\w.])(-?\d+(?:[.,]\d+)?)\s*(%|min(?:utos?)?\b)?")
_TOPICS = {"censur": "pct_censored", "distrac": "pct_first_is_distraction"}


def _collect(obj, key: str, out: dict[str, set[float]]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out["any"].add(float(obj))
        if key.startswith("pct_"):
            out["pct"].add(float(obj))
            out.setdefault(key, set()).add(float(obj))
        if "min" in key.split("_"):
            out["min"].add(float(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _collect(v, str(k), out)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, key, out)


def allowed_numbers(snapshot: Snapshot, h: Hypothesis) -> dict[str, set[float]]:
    out: dict[str, set[float]] = {"any": set(), "pct": set(), "min": set()}
    _collect(snapshot.data, "", out)
    r = h.expected_ratio
    from_ratio = {round(100 * r), round(100 * (1 - r)), round(100 * (1 - r), 1), round(100 * r, 1)}
    out["pct"] |= from_ratio
    out["any"] |= from_ratio | {r}
    return out


def _matches(x: float, allowed: set[float]) -> bool:
    return any(abs(x - v) <= 0.051 + 0.005 * abs(v) for v in allowed)


def verify(h: Hypothesis, snapshot: Snapshot) -> ToolVerdict:
    ids = {r["block_id"] for r in snapshot.rows}
    unknown = [b for b in h.cited_block_ids if b not in ids]
    text = _IGNORE.sub(" ", h.rationale)
    allowed = allowed_numbers(snapshot, h)
    invented = []
    for clause in re.split(r"[;:()]|\.(?!\d)|,\s", text):          # el punto decimal no corta
        low = clause.lower()
        marks = [(m.start(), key) for word, key in _TOPICS.items() for m in re.finditer(word, low)]
        for m in _NUM.finditer(clause):
            num, unit = m.group(1), m.group(2)
            kind = "pct" if unit == "%" else "min" if unit else "any"
            pool = allowed[kind]
            if kind == "pct" and marks:                               # el tema más cercano en el texto
                topic = min(marks, key=lambda t: abs(t[0] - m.start()))[1]
                pool = allowed.get(topic, set())
            if not _matches(float(num.replace(",", ".")), pool):
                invented.append(num + (unit if unit == "%" else f" {unit}" if unit else ""))
    problems = []
    if unknown:
        problems.append(f"block_id inexistentes: {', '.join(unknown[:3])}")
    if invented:
        problems.append(f"cifras fuera del snapshot: {', '.join(invented[:5])}")
    if problems:
        return ToolVerdict(name="verifier", passed=False, detail="; ".join(problems)[:400])
    return ToolVerdict(name="verifier", passed=True,
                       detail=f"{len(h.cited_block_ids)} block_id citados existen; cifras derivables del snapshot")
