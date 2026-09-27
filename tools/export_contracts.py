"""Genera contracts/schemas/*.schema.json y contracts/openapi.json desde core/contracts.py y las rutas.

    .venv\Scripts\python tools/export_contracts.py          # escribe
    .venv\Scripts\python tools/export_contracts.py --check  # exit 1 si hay diferencias (lo usa el test)

Solo el Frente 0 corre esto con escritura. Los demás frentes lo usan con --check.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.app import create_app  # noqa: E402
from core.contracts import EXPORTED  # noqa: E402

SCHEMAS = ROOT / "contracts" / "schemas"
OPENAPI = ROOT / "contracts" / "openapi.json"


def dump(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def rendered() -> dict[Path, str]:
    out = {}
    for name, model in EXPORTED.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://n-de-1.local/contracts/{name}.schema.json"
        out[SCHEMAS / f"{name}.schema.json"] = dump(schema)
    with tempfile.TemporaryDirectory() as d:
        out[OPENAPI] = dump(create_app(Path(d), token="export").openapi())
    return out


def main(argv: list[str]) -> int:
    files = rendered()
    if "--check" in argv:
        stale = [p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        extra = [p for p in SCHEMAS.glob("*.schema.json") if p not in files]
        for p in stale + extra:
            print(f"desincronizado: {p.relative_to(ROOT)}")
        return 1 if stale or extra else 0
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    for p in SCHEMAS.glob("*.schema.json"):
        if p not in files:
            p.unlink()
    for p, text in files.items():
        p.write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(files)} archivos de contrato escritos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
