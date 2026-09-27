"""`python -m core.simulate --out demo-data --weeks 5 --seed 7`: datos SINTÉTICOS para la demo."""
from __future__ import annotations

import argparse
from pathlib import Path

from core.simulate.engine import simulate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m core.simulate")
    ap.add_argument("--out", type=Path, required=True, help="data_dir nuevo (vacío o inexistente)")
    ap.add_argument("--weeks", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--effect", type=float, default=0.5, help="efecto VERDADERO de la intervención (factor)")
    ap.add_argument("--llm", choices=("off", "cache", "live"), default="off")
    a = ap.parse_args(argv)
    r = simulate(a.out, weeks=a.weeks, seed=a.seed, true_effect=a.effect, llm=a.llm)
    print(f"DATOS SINTÉTICOS en {r.out}: {r.days} días, {r.blocks} bloques, tramos de {r.synth}")
    print(f"experimento: {r.experiment_id or '—'} · veredicto: {r.verdict or 'sin resolver'}")
    print(f"abrí la app sobre estos datos: NDE1_DATA_DIR={r.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
