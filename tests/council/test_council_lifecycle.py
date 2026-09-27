"""De punta a punta en el consejo: reunión → preregistro → sorteo del runtime → outcomes → resolución.

El runtime real es del Frente B; acá se reproduce su contrato exacto (brief-b: `permuted_arm` con la
semilla del `ActiveExperiment`, `draw_index` consecutivo, `outcome` final y luego `after_outcome`).
Los datos son SINTÉTICOS (ver conftest).
"""
import json
from datetime import timedelta

import pytest

from core.contracts import Arm, permuted_arm, seed_commitment
from core.council.council import Council, SeedStore
from core.council.experiments import ExperimentError, Experiments
from core.council.journal_view import JournalView
from core.llm import OpenAICompatClient
from tests.council.conftest import BASE_DAY, write_block


def offline_factory(tmp_path):
    """Ollama sin respuestas grabadas: cada llamada falla con LLMError, como un Ollama caído."""
    return lambda role, model: OpenAICompatClient.for_ollama("http://127.0.0.1:9/v1", model, mode="replay",
                                                             cassette_dir=tmp_path / "vacio")


@pytest.fixture
def council(baseline, tmp_path, settings):
    seeds = SeedStore(tmp_path)
    return (Council(baseline, lambda: settings, seeds, offline_factory(tmp_path)),
            Experiments(baseline, lambda: settings, seeds))


def test_without_llm_the_fallback_preregisters_a_detectable_effect(council, baseline, tmp_path):
    c, exps = council
    run = c.run()
    assert not run.llm_used and "Scout no disponible" in run.fallback_reason
    assert len(run.proposals) == 4 and all(p.source == "allocator_fallback" for p in run.proposals)
    view = JournalView.load(baseline)
    p = view.active_prereg()
    assert p is not None and p.experiment_id == run.chosen_experiment_id
    assert p.source in ("allocator_fallback", "exploration_vetoed") and 0.3 <= p.hypothesis.expected_ratio < 1
    assert p.red_team.premortem == ""                          # el LLM del Red Team tampoco respondió
    seed = json.loads((tmp_path / "council" / "seeds" / f"{p.experiment_id}.json").read_text())["seed_hex"]
    assert seed_commitment(seed) == p.seed_commitment
    assert seed not in (tmp_path / "journal.jsonl").read_text(encoding="utf-8")   # la semilla no se filtra
    assert c.run().fallback_reason == "ya hay un experimento en curso"          # uno a la vez


def test_insufficient_baseline_records_the_run_without_preregistering(journal, tmp_path, settings):
    write_block(journal, 1, BASE_DAY.replace(hour=9), "escritura", 900.0, "other")
    run = Council(journal, lambda: settings, SeedStore(tmp_path), offline_factory(tmp_path)).run()
    assert run.chosen_experiment_id is None and "insuficiente" in run.fallback_reason
    assert JournalView.load(journal).runs == [run]


def simulate_runtime(journal, exps, n_blocks, treat_latency, control_latency, start_index=1000):
    """Lo que hace el Frente B por cada bloque: sortear con la referencia, escribir el outcome, avisar."""
    exp = exps.active()
    for k in range(n_blocks):
        arm = permuted_arm(exp.seed_hex, exp.experiment_id, k, exp.treatment)
        lat = treat_latency(k) if arm != Arm.control else control_latency(k)
        day = BASE_DAY + timedelta(days=30 + k // 2)
        bid = write_block(journal, start_index + k, day.replace(hour=9 if k % 2 == 0 else 15), "escritura", lat,
                          "other", arm=arm, experiment_id=exp.experiment_id, draw_index=k)
        exps.after_outcome(JournalView.load(journal).outcomes[bid])
        if exp.experiment_id in JournalView.load(journal).resolutions:
            break                                   # con N impar, los bloques de 4 pueden necesitar alguno más
    return exp


def test_full_lifecycle_resolves_at_n_and_reveals_the_committed_seed(council, baseline):
    c, exps = council
    c.run()
    exp = exps.active()
    n = exp.n_per_arm
    prog = exps.progress()
    assert prog.n_control_done == prog.n_treatment_done == 0
    assert not {"p_value", "ratio", "median_control_s"} & set(prog.model_dump())     # sin efecto antes del N
    simulate_runtime(baseline, exps, 2 * n + 8, treat_latency=lambda k: 300.0 + k, control_latency=lambda k: 1500.0 + k)
    view = JournalView.load(baseline)
    r = view.resolutions[exp.experiment_id]
    assert r.verdict == "supported" and min(r.n_control, r.n_treatment) == n
    assert seed_commitment(r.seed_revealed) == view.prereg(exp.experiment_id).seed_commitment
    assert exps.active() is None and exps.progress() is None
    led = {e.intervention: e for e in exps.ledger()}
    assert led[exp.treatment].n_supported == 1
    assert baseline.verify() > 0


def test_no_effect_is_not_supported(council, baseline):
    c, exps = council
    c.run()
    n = exps.active().n_per_arm
    same = lambda k: 900.0 + 37 * (k % 11)                   # nulo de verdad: la condición no cambia nada
    simulate_runtime(baseline, exps, 2 * n + 8, treat_latency=same, control_latency=same)
    r = list(JournalView.load(baseline).resolutions.values())[0]
    assert r.verdict == "not_supported" and r.p_value > r.alpha


def test_a_tampered_assignment_blocks_the_resolution(council, baseline):
    c, exps = council
    c.run()
    exp = exps.active()
    wrong = [Arm.control if permuted_arm(exp.seed_hex, exp.experiment_id, 0, exp.treatment) != Arm.control
             else exp.treatment]
    write_block(baseline, 5000, BASE_DAY + timedelta(days=40), "escritura", 100.0, "other", arm=wrong[0],
                experiment_id=exp.experiment_id, draw_index=0)
    with pytest.raises(ExperimentError, match="el sorteo dice"):
        exps._resolve(JournalView.load(baseline), exp.experiment_id)


def test_missing_seed_falls_back_to_baseline_instead_of_breaking_the_runtime(council, tmp_path):
    c, exps = council
    c.run()
    for f in (tmp_path / "council" / "seeds").glob("*.json"):
        f.unlink()
    assert exps.active() is None
