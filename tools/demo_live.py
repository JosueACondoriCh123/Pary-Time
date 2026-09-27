"""Prepara un directorio de demo con un bloque confirmado y el brazo forzado.

No es el sorteo: no llama a `permuted_arm`. Sirve solo para el guion en vivo, en un
directorio marcado `DATA_LABEL=sintetico`, nunca en los datos reales de la persona.

    python tools/demo_live.py --data-dir demo-live --in 2m --arm retrasar_distracciones

Después hay que arrancar la app con NDE1_DATA_DIR apuntando a ese directorio.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.contracts import (Arm, Assignment, BlockConfirmed, BlockCreate, Settings, Target, TaskKind,
                            WorkMatcher)
from core.interfaces import AppContext
from core.journal import Journal, LoopLock, LoopLockError, append_typed
from core.runtime import build

LABEL = "sintetico"


class DemoDirError(Exception):
    pass


def protected_roots() -> list[Path]:
    """Carpetas de la app instalada. No todo AppData: Temp vive ahí y es un directorio de prueba válido."""
    names = ("Consejo N-de-1", "consejo-n-de-1", "nde1-app")
    roots = []
    for key in ("APPDATA", "LOCALAPPDATA"):
        value = os.environ.get(key)
        if value:
            base = Path(value)
            roots.extend(base / name for name in names)
    return roots


def parse_in(text: str) -> int:
    match = re.fullmatch(r"(\d+)(ms|s|m|h)", text.strip())
    if not match:
        raise DemoDirError("--in espera algo como 30s, 2m o 1h")
    amount, unit = int(match.group(1)), match.group(2)
    return amount * {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000}[unit]


def assert_demo_dir(path: Path, roots: list[Path] | None = None) -> Path:
    """Rechaza datos reales. Escribe el marcador solo después de esas comprobaciones."""
    path = Path(path).resolve()
    for root in roots if roots is not None else protected_roots():
        if path == root or root in path.parents:
            raise DemoDirError(f"rechazado: {path} está dentro de datos reales ({root})")
    if path.name == "data" and (path.parent / "pyproject.toml").exists():
        raise DemoDirError("usa un directorio de demo (demo-live), no data/ del desarrollo")
    marker = path / "DATA_LABEL"
    journal = path / "journal.jsonl"
    if marker.exists() and marker.read_text(encoding="utf-8").strip() != LABEL:
        raise DemoDirError("rechazado: DATA_LABEL no es sintetico")
    if journal.exists() and not marker.exists():
        raise DemoDirError("rechazado: hay un journal sin marcador de demo")
    path.mkdir(parents=True, exist_ok=True)
    marker.write_text(LABEL + "\n", encoding="utf-8")
    return path


def prepare(data_dir: Path, start_in_ms: int, arm: Arm, now_ms: int | None = None,
            roots: list[Path] | None = None, label: str = "Demo en vivo",
            first_step: str | None = None):
    """Crea el bloque confirmado. El brazo es el pedido: no sale de la lotería."""
    path = assert_demo_dir(data_dir, roots)
    if start_in_ms < 0:
        raise DemoDirError("--in no puede ser negativo")
    if first_step and arm != Arm.primer_paso:
        raise DemoDirError("--first-step solo vale con --arm primer_paso")
    lock = LoopLock(path / "core.lock")
    try:
        lock.acquire()
    except LoopLockError as exc:
        raise DemoDirError("el núcleo está usando ese directorio; cerralo y volvé a correr el script") from exc
    try:
        now = int(datetime.now().timestamp() * 1000) if now_ms is None else now_ms
        start = now + start_in_ms
        ctx = AppContext(Journal(path / "journal.jsonl"), lambda: Settings(), path)

        class Clock:
            def now_ms(self) -> int:
                return now

        service = build(ctx, Clock())
        try:
            created = service.create_block(BlockCreate(
                local_date=datetime.fromtimestamp(start / 1000).date().isoformat(),
                planned_start_ms=start,
                planned_minutes=25,
                task_kind=TaskKind.otro,
                task_label=label,
                target=Target(kind="none"),
                work_matchers=[WorkMatcher(field="process", pattern="nde1-demo")],
            ))
            service.store.mark_confirmed(created.block_id)
            block = service.store.get(created.block_id).block
            append_typed(ctx.journal, "block_confirmed", BlockConfirmed(
                block_id=block.block_id, local_date=block.local_date,
                planned_start_ms=block.planned_start_ms, planned_minutes=block.planned_minutes,
                task_kind=block.task_kind,
            ))
            service.store.save_assignment(block.block_id, arm, None, None, now)
            append_typed(ctx.journal, "assignment", Assignment(
                block_id=block.block_id, experiment_id=None, arm=arm, draw_index=None, assigned_ms=now,
            ))
            if first_step:
                service.store.set_first_step(block.block_id, first_step)
            view = service._view(service.store.get(block.block_id))
        finally:
            service.stop()
        return view
    finally:
        lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/demo_live.py")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--in", dest="start_in", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--label", default="Demo en vivo")
    parser.add_argument("--first-step", default=None)
    args = parser.parse_args(argv)
    try:
        arm = Arm(args.arm)
        view = prepare(args.data_dir, parse_in(args.start_in), arm, label=args.label,
                       first_step=args.first_step)
    except (DemoDirError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    when = datetime.fromtimestamp(view.planned_start_ms / 1000).strftime("%H:%M:%S")
    print(f"demo lista en {args.data_dir.resolve()}")
    print(f"bloque {view.block_id}  brazo {arm.value}  empieza {when}")
    print("DATA_LABEL=sintetico")
    print(f"arrancá la app con NDE1_DATA_DIR={args.data_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
