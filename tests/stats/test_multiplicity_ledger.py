import pytest

from core.contracts import Arm
from core.stats.ledger import build_ledger, posterior_mean
from core.stats.multiplicity import initial_wealth, next_alpha, wealth_after


def test_first_hypothesis_spends_half_of_the_initial_wealth():
    assert initial_wealth(0.05) == pytest.approx(0.0475)
    assert next_alpha([], 0.05) == pytest.approx(0.02375)


def test_a_discovery_earns_alpha_back_and_a_miss_spends_it():
    a1 = next_alpha([], 0.05)
    after_hit = next_alpha([(a1, True)], 0.05)
    after_miss = next_alpha([(a1, False)], 0.05)
    assert after_hit > a1 > after_miss
    assert wealth_after([(a1, True)], 0.05) == pytest.approx(0.0475 - a1 / (1 - a1) + 0.05)


def test_wealth_never_goes_negative_and_alpha_decays_after_many_misses():
    hist = []
    for _ in range(12):
        hist.append((next_alpha(hist, 0.05), False))
    assert wealth_after(hist, 0.05) >= 0
    assert next_alpha(hist, 0.05) < 0.001


def test_ledger_counts_only_informative_verdicts_per_intervention():
    led = {e.intervention: e for e in build_ledger([
        (Arm.retrasar_distracciones, "supported"), (Arm.retrasar_distracciones, "not_supported"),
        (Arm.retrasar_distracciones, "supported"), (Arm.cuenta_regresiva, "insufficient"),
        (Arm.control, "supported"),
    ])}
    r = led[Arm.retrasar_distracciones]
    assert (r.alpha, r.beta, r.n_resolved, r.n_supported) == (3, 2, 3, 2)
    assert posterior_mean(r) == pytest.approx(0.6)
    assert led[Arm.cuenta_regresiva].n_resolved == 0 and Arm.control not in led
    assert len(led) == 4
