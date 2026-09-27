from datetime import timedelta

from core.contracts import Hypothesis, Moderator, Settings
from core.council.journal_view import JournalView
from core.council.red_team import (confounders_tool, constitution_tool, multiplicity_tool, power_tool,
                                   run_tools)
from core.council.snapshot import build_snapshot
from tests.council.conftest import BASE_DAY, write_block


def hyp(intervention="retrasar_distracciones", moderator=("time_of_day", "morning"), ratio=0.5):
    mod = Moderator(kind=moderator[0], value=moderator[1]) if moderator else None
    return Hypothesis(intervention=intervention, moderator=mod, expected_ratio=ratio, rationale="x",
                      cited_block_ids=[])


def ctx(journal):
    v = JournalView.load(journal)
    return v, build_snapshot(v)


def test_power_passes_with_a_clear_effect_and_vetoes_a_tiny_one(baseline):
    v, s = ctx(baseline)
    ok, plan = power_tool(hyp(moderator=None, ratio=0.4), s, v, alpha=0.02375)
    assert ok.passed and plan.n_per_arm >= 4 and plan.weeks_needed <= 3, ok.detail
    tiny, _ = power_tool(hyp(moderator=None, ratio=0.9), s, v, alpha=0.02375)
    assert not tiny.passed and "tope" in tiny.detail


def test_a_moderator_with_one_block_per_day_is_too_slow_to_test(baseline):
    """Compromiso real del N-de-1: restringir a mañanas deja 7 bloques/semana y el mismo efecto pide
    más de 3 semanas. El Red Team lo veta por potencia (evidencia débil: explorable)."""
    v, s = ctx(baseline)
    verdict, plan = power_tool(hyp(ratio=0.4), s, v, alpha=0.02375)
    assert not verdict.passed and "7.0 bloques elegibles/semana" in verdict.detail
    assert plan is not None and plan.weeks_needed > 3


def test_power_vetoes_without_enough_baseline(journal):
    for i in range(3):
        write_block(journal, i, BASE_DAY.replace(hour=9), "escritura", 900.0, "other")
    v, s = ctx(journal)
    verdict, plan = power_tool(hyp(), s, v, alpha=0.02)
    assert not verdict.passed and "insuficiente" in verdict.detail and plan is None


def test_confounders_veto_a_moderator_that_is_really_a_weekday(journal):
    for i in range(8):                                # todas las mañanas caen en lunes
        write_block(journal, i, (BASE_DAY + timedelta(weeks=i)).replace(hour=9), "escritura", 900.0, "other")
        write_block(journal, 100 + i, (BASE_DAY + timedelta(weeks=i, days=i % 5)).replace(hour=15), "lectura",
                    300.0, "other")
    v, s = ctx(journal)
    c = confounders_tool(hyp(), s)
    assert not c.passed and "weekday=lun" in c.detail
    assert confounders_tool(hyp(moderator=None), s).passed


def test_baseline_fixture_moderator_is_not_confounded(baseline):
    assert confounders_tool(hyp(), ctx(baseline)[1]).passed


def test_multiplicity_uses_alpha_investing(baseline):
    v, _ = ctx(baseline)
    t, a = multiplicity_tool(v, Settings())
    assert t.passed and abs(a - 0.02375) < 1e-9


def test_constitution_forbids_high_friction_above_the_cap(baseline):
    v, _ = ctx(baseline)
    strict = Settings(high_friction_max_fraction=0.3)
    assert not constitution_tool(hyp(), v, strict).passed
    assert constitution_tool(hyp(intervention="cuenta_regresiva"), v, strict).passed


def test_run_tools_reports_all_five_tools(baseline):
    v, s = ctx(baseline)
    tools, plan = run_tools(hyp(moderator=None, ratio=0.4), s, v, Settings(), check_citations=False)
    assert [t.name for t in tools] == ["verifier", "power", "confounders", "multiplicity", "constitution"]
    assert all(t.passed for t in tools) and plan is not None, [t.detail for t in tools]
