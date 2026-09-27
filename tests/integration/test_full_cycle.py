"""Ciclo completo con el código real y reloj acelerado (core.simulate): línea base → consejo → preregistro →
sorteo → intervenciones → outcomes → resolución con la semilla revelada. Datos SINTÉTICOS.

Es la prueba de que las piezas de los 4 frentes cierran el ciclo, y la que detectó que el test @1 (mediana
agrupada) perdía el efecto cuando se mezclan mañanas y tardes: de ahí el test @2 estratificado.
"""
import pytest
from fastapi.testclient import TestClient

from core.app import create_app
from core.contracts import permuted_arm, seed_commitment
from core.council.journal_view import JournalView
from core.journal import Journal
from core.simulate import simulate


@pytest.fixture(scope="module")
def with_effect(tmp_path_factory):
    out = tmp_path_factory.mktemp("sim") / "demo-data"
    return simulate(out, weeks=5, seed=2, true_effect=0.5)       # 1 y 7 son los 2 de 10 que no alcanzan (ver README)


def test_a_true_effect_is_found_with_the_preregistered_stratified_test(with_effect):
    j = Journal(with_effect.out / "journal.jsonl")
    assert j.verify() > 0
    view = JournalView.load(j)
    p = view.preregs[0]
    assert p.test == "permutation_meanlog_diff_stratified@2"
    r = view.resolutions[p.experiment_id]
    assert r.verdict == "supported" and r.p_value <= r.alpha and r.ratio < 0.8
    assert seed_commitment(r.seed_revealed) == p.seed_commitment
    for a in view.assignments.values():                  # el sorteo sellado coincide con la semilla revelada
        if a.experiment_id == p.experiment_id:
            assert a.arm == permuted_arm(r.seed_revealed, p.experiment_id, a.draw_index, p.arms[1])


def test_the_app_opens_the_simulated_data_labeled_as_synthetic(with_effect):
    with TestClient(create_app(with_effect.out, "tok")) as cl:
        h = {"X-NDE1-Token": "tok"}
        assert cl.get("/health").json()["data_label"] == "sintetico"
        rep = cl.get("/report", headers=h).json()
        assert rep["journal"]["ok"] and any(e["resolution"] for e in rep["experiments"])
        assert cl.get("/journal/verify", headers=h).json()["ok"]


def test_no_effect_means_no_false_discovery(tmp_path):
    r = simulate(tmp_path / "null", weeks=5, seed=7, true_effect=1.0)
    assert r.verdict == "not_supported"


def test_simulation_never_overwrites_an_existing_data_dir(tmp_path):
    (tmp_path / "journal.jsonl").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        simulate(tmp_path, weeks=1)
