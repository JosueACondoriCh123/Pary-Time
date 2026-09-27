"""La fórmula de N (power.py) contra el test de permutación real sobre datos SINTÉTICOS."""
import math

import pytest

from core.stats.power import feasibility, required_n_per_arm, sigma_log
from core.stats.simulation import rejection_rate


def test_required_n_grows_with_noise_and_shrinks_with_effect():
    base = required_n_per_arm(0.7, 0.6, 0.025)
    assert required_n_per_arm(1.0, 0.6, 0.025) > base
    assert required_n_per_arm(0.7, 0.4, 0.025) < base
    assert required_n_per_arm(0.7, 0.6, 0.01) > base
    assert required_n_per_arm(0.01, 0.1, 0.05) == 4                  # piso


@pytest.mark.parametrize("ratio", [0, 1, 1.2])
def test_only_reductions_are_testable(ratio):
    with pytest.raises(ValueError):
        required_n_per_arm(0.7, ratio, 0.05)


def test_sigma_log_needs_two_blocks():
    assert sigma_log([300, 300]) == 0
    with pytest.raises(ValueError):
        sigma_log([300])


def test_feasibility_vetoes_when_the_experiment_would_take_too_long():
    ok = feasibility(0.6, 0.5, 0.025, eligible_blocks_per_week=15)
    assert ok.feasible and ok.weeks_needed == pytest.approx(2 * ok.n_per_arm / 15)
    slow = feasibility(1.2, 0.8, 0.0125, eligible_blocks_per_week=10)
    assert not slow.feasible and "tope" in slow.detail
    assert not feasibility(0.6, 0.5, 0.025, eligible_blocks_per_week=0).feasible


def test_false_positive_rate_of_the_real_test_stays_near_alpha():
    sim = rejection_rate(n_per_arm=14, median_s=900, sigma=0.8, ratio=1.0, alpha=0.05, reps=500, seed=11)
    se = math.sqrt(0.05 * 0.95 / sim.reps)
    assert sim.rejection_rate <= 0.05 + 3 * se


def test_n_from_the_formula_reaches_the_promised_power_in_simulation():
    sigma, ratio, alpha = 0.7, 0.5, 0.025
    n = required_n_per_arm(sigma, ratio, alpha, power=0.8)
    sim = rejection_rate(n_per_arm=n, median_s=900, sigma=sigma, ratio=ratio, alpha=alpha, reps=400, seed=5)
    se = math.sqrt(0.8 * 0.2 / sim.reps)
    assert sim.rejection_rate >= 0.8 - 3 * se, f"N={n}: potencia simulada {sim.rejection_rate:.2f}"
