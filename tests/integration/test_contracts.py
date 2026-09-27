import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from core import contracts as c

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "contracts" / "examples").glob("*.json"))


def test_exported_schemas_and_openapi_are_in_sync():
    r = subprocess.run([sys.executable, "tools/export_contracts.py", "--check"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_every_example_validates_against_its_json_schema_and_model(path):
    name = path.stem.split(".")[0]
    schema = json.loads((ROOT / "contracts" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data if isinstance(data, list) else [data]:
        jsonschema.validate(item, schema)
        c.EXPORTED[name].model_validate(item)


def test_models_reject_unknown_fields():
    with pytest.raises(Exception):
        c.FirstStep.model_validate({"text": "abrir el doc", "extra": 1})


def test_reference_randomization_is_deterministic_and_balanced_per_block_of_four():
    seed = "ab" * 32
    a = [c.permuted_arm(seed, "exp_x", i, c.Arm.cuenta_regresiva) for i in range(40)]
    b = [c.permuted_arm(seed, "exp_x", i, c.Arm.cuenta_regresiva) for i in range(40)]
    assert a == b
    for j in range(0, 40, 4):
        assert a[j:j + 4].count(c.Arm.control) == 2
    other = [c.permuted_arm("cd" * 32, "exp_x", i, c.Arm.cuenta_regresiva) for i in range(40)]
    assert other != a                                   # otra semilla, otra secuencia


def test_seed_commitment_matches_sha256_of_raw_seed_bytes():
    import hashlib
    seed = "01" * 32
    assert c.seed_commitment(seed) == hashlib.sha256(bytes.fromhex(seed)).hexdigest()


def _field_names(schema) -> set[str]:
    names = set()
    if isinstance(schema, dict):
        names |= set(schema.get("properties", {}))
        for v in schema.values():
            names |= _field_names(v)
    elif isinstance(schema, list):
        for v in schema:
            names |= _field_names(v)
    return names


def test_journal_payloads_never_carry_user_text_fields():
    """El journal se comparte con un profesional: ningún payload puede tener títulos ni textos."""
    banned = ("title", "task_label", "first_step", "work_matchers", "target")
    for kind, model in c.JOURNAL_PAYLOADS.items():
        if model is None:
            continue
        for name in _field_names(model.model_json_schema()):
            assert not any(b in name for b in banned), f"{kind} expone {name}"
