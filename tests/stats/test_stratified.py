"""Test @2: diferencia ponderada dentro de franjas. Datos SINTÉTICOS con estructura conocida."""
import numpy as np

from core.stats.stratified import stratified_test


def test_imbalance_across_strata_does_not_hide_the_effect():
    """Caso real de la simulación: tratamiento cargado de mañanas lentas, control de tardes rápidas.
    Dentro de cada franja el tratamiento arranca en la mitad de tiempo: el ratio tiene que dar ~0.5."""
    rng = np.random.default_rng(3)
    am_c = np.exp(rng.normal(np.log(1600), 0.3, 8)); am_t = np.exp(rng.normal(np.log(800), 0.3, 14))
    pm_c = np.exp(rng.normal(np.log(600), 0.3, 14)); pm_t = np.exp(rng.normal(np.log(300), 0.3, 8))
    r = stratified_test(list(am_c) + list(pm_c), ["am"] * 8 + ["pm"] * 14,
                        list(am_t) + list(pm_t), ["am"] * 14 + ["pm"] * 8, seed=1)
    assert 0.4 < r.ratio < 0.65 and r.p_value < 0.01


def test_no_effect_with_imbalance_is_not_significant():
    rng = np.random.default_rng(5)
    am = lambda n: list(np.exp(rng.normal(np.log(1600), 0.4, n)))   # noqa: E731
    pm = lambda n: list(np.exp(rng.normal(np.log(600), 0.4, n)))    # noqa: E731
    r = stratified_test(am(8) + pm(14), ["am"] * 8 + ["pm"] * 14, am(14) + pm(8), ["am"] * 14 + ["pm"] * 8, seed=2)
    assert r.p_value > 0.05 and 0.7 < r.ratio < 1.4


def test_same_inputs_same_p_and_single_arm_strata_weigh_nothing():
    a = stratified_test([900, 1000, 50], ["am", "am", "noche"], [400, 500], ["am", "am"], seed=9)
    b = stratified_test([900, 1000, 50], ["am", "am", "noche"], [400, 500], ["am", "am"], seed=9)
    assert a == b and a.ratio < 0.6                       # el bloque de "noche" (solo control) no cuenta
