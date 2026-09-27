"""Verificador: toda cifra de la justificación tiene que estar en el snapshot o en la propia hipótesis.

Mismo espíritu que Night Council: el modelo puede razonar, pero no puede traer números de afuera. Las
cifras aceptadas son: cualquier número del snapshot (filas y `facts`), el `expected_ratio` y su lectura en
porcentaje. Se ignoran ids de bloque, fechas y horas (no son afirmaciones cuantitativas).
"""
from __future__ import annotations

import re

from core.contracts import Hypothesis, ToolVerdict
from core.council.snapshot import Snapshot

_IGNORE = re.compile(r"blk_[0-9a-f]{12}|\d{4}-\d{2}-\d{2}|\b\d{1,2}:\d{2}\b")
_NUM = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?")


def _numbers_in(obj, out: set[float]) -> set[float]:
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers_in(v, out)
    return out


def allowed_numbers(snapshot: Snapshot, h: Hypothesis) -> set[float]:
    nums = _numbers_in(snapshot.data, set())
    r = h.expected_ratio
    nums |= {r, round(100 * r), round(100 * (1 - r)), round(100 * (1 - r), 1), round(100 * r, 1)}
    return nums


def _matches(x: float, allowed: set[float]) -> bool:
    return any(abs(x - v) <= 0.051 + 0.005 * abs(v) for v in allowed)


def verify(h: Hypothesis, snapshot: Snapshot) -> ToolVerdict:
    ids = {r["block_id"] for r in snapshot.rows}
    unknown = [b for b in h.cited_block_ids if b not in ids]
    text = _IGNORE.sub(" ", h.rationale)
    allowed = allowed_numbers(snapshot, h)
    invented = [m for m in _NUM.findall(text) if not _matches(float(m.replace(",", ".")), allowed)]
    problems = []
    if unknown:
        problems.append(f"block_id inexistentes: {', '.join(unknown[:3])}")
    if invented:
        problems.append(f"cifras fuera del snapshot: {', '.join(invented[:5])}")
    if problems:
        return ToolVerdict(name="verifier", passed=False, detail="; ".join(problems)[:400])
    return ToolVerdict(name="verifier", passed=True,
                       detail=f"{len(h.cited_block_ids)} block_id citados existen; cifras derivables del snapshot")
