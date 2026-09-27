import numpy as np
import pytest
from scipy import stats as sps

from core.stats.permutation import latency_values, permutation_test, seed_from


def scipy_p(c, t, n_resamples=np.inf, seed=0):
    r = sps.permutation_test((c, t), lambda x, y: np.median(x) - np.median(y), permutation_type="independent",
                             alternative="greater", n_resamples=n_resamples, rng=np.random.default_rng(seed),
                             vectorized=False)
    return r.pvalue


@pytest.mark.parametrize("c,t", [
    ([900, 1320, 400, 5400, 780], [300, 420, 610, 1200, 95]),
    ([60, 60, 120, 5400, 5400, 300], [60, 30, 45, 5400, 20, 10]),          # empates y censurados
    ([100, 200, 300, 400], [100, 200, 300, 400]),                          # idénticos
    ([10, 20, 30], [4000, 5000, 5400, 5400]),                              # efecto al revés
])
def test_exact_p_value_matches_scipy(c, t):
    ours = permutation_test(c, t)
    assert ours.exact
    assert ours.p_value == pytest.approx(scipy_p(c, t), abs=1e-12)


def test_monte_carlo_p_value_agrees_with_scipy_on_a_large_sample():
    rng = np.random.default_rng(7)
    c = np.exp(rng.normal(np.log(1200), 0.8, 16))
    t = np.exp(rng.normal(np.log(600), 0.8, 16))
    ours = permutation_test(c, t, n_resamples=20_000, seed=1)
    assert not ours.exact
    assert ours.p_value == pytest.approx(scipy_p(c, t, n_resamples=20_000, seed=2), abs=0.01)


def test_monte_carlo_is_reproducible_with_the_same_seed_and_never_returns_zero():
    c, t = [1000.0 + i for i in range(15)], [float(i) for i in range(15)]   # separados, sin empates
    a = permutation_test(c, t, seed=seed_from("exp_0123456789ab"), max_exact=0)
    b = permutation_test(c, t, seed=seed_from("exp_0123456789ab"), max_exact=0)
    assert a == b
    assert 0 < a.p_value < 0.001            # la mediana solo mira el centro: alguna permutación puede empatar


def test_censored_blocks_count_as_the_censor_value():
    v = latency_values([420.0, None, 7000.0], [False, True, False], 5400)
    assert v.tolist() == [420.0, 5400.0, 5400.0]
    with pytest.raises(ValueError):
        latency_values([None], [False], 5400)


def test_empty_arm_is_an_error():
    with pytest.raises(ValueError):
        permutation_test([], [1.0])


def test_heavy_ties_make_the_median_coarse_on_purpose():
    """Con brazos de valores idénticos, media partición empata el estadístico: p ≈ 0.5. Es una
    propiedad de la mediana (y la razón de que muchos censurados le quiten potencia), no un bug."""
    r = permutation_test([5400] * 15, [0.0] * 15, max_exact=0)
    assert 0.45 < r.p_value < 0.55
