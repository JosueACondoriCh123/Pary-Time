"""El consejo con los modelos reales de Ollama.

  * `NDE1_LIVE_TESTS=1`: llama a Ollama (Scout qwen3.5:4b, Red Team granite4.2:8b) y GRABA las respuestas en
    `data/cassettes/` (solo contienen el snapshot sintético de conftest: ningún dato personal).
  * Siempre: reproduce esas cassettes. Sin cassettes se saltea con el comando para grabarlas.

Lo que el modelo diga puede no pasar el verificador o el Red Team: eso es un resultado, no un fallo del test.
Lo que se exige es que el circuito sea auditable: llamada registrada, hipótesis del contrato, 5 herramientas.
"""
import os
from pathlib import Path

import pytest

from core.contracts import Settings
from core.council.council import Council, SeedStore
from core.council.journal_view import JournalView
from core.llm import OpenAICompatClient

CASSETTES = Path(__file__).resolve().parents[2] / "data" / "cassettes"
LIVE = os.getenv("NDE1_LIVE_TESTS") == "1"


def factory(mode):
    s = Settings()
    return lambda role, model: OpenAICompatClient.for_ollama(s.ollama_base_url, model, mode=mode,
                                                             cassette_dir=CASSETTES, timeout=600)


def run_council(journal, tmp_path, mode):
    ids = iter(["0000000000a1", "0000000000b2"])            # run_id fijo: la exploración es reproducible
    return Council(journal, Settings, SeedStore(tmp_path), factory(mode), new_id=lambda: next(ids)).run()


def check_auditable(run, journal):
    assert run.llm_used and run.models == {"scout": "qwen3.5:4b", "red_team": "granite4.2:8b"}
    assert run.proposals, run.fallback_reason
    for p in run.proposals:
        assert [t.name for t in p.red_team.tools] == ["verifier", "power", "confounders", "multiplicity",
                                                       "constitution"]
    assert JournalView.load(journal).runs[-1].run_id == run.run_id
    assert journal.verify() > 0


@pytest.mark.live
@pytest.mark.skipif(not LIVE, reason="en vivo: NDE1_LIVE_TESTS=1 con Ollama corriendo y los modelos bajados")
def test_live_council_records_real_answers(baseline, tmp_path):
    run = run_council(baseline, tmp_path, "record")
    check_auditable(run, baseline)
    print("\n" + "\n".join(f"[{p.source}] {p.hypothesis.intervention.value} r={p.hypothesis.expected_ratio} "
                           f"→ {p.red_team.verdict}: " + "; ".join(t.detail for t in p.red_team.tools if not t.passed)
                           for p in run.proposals))


def test_replayed_council_is_identical_and_auditable(baseline, tmp_path):
    if not any(CASSETTES.glob("*.json")):
        pytest.skip("sin cassettes: grabalas con NDE1_LIVE_TESTS=1 pytest tests/council/test_ollama_council.py")
    a = run_council(baseline, tmp_path / "a", "replay")
    check_auditable(a, baseline)
    assert a.proposals[0].source == "scout"
    chosen = [p for p in a.proposals if p.red_team.premortem]
    if a.chosen_experiment_id:                                   # el Red Team LLM opinó sobre lo elegido
        assert len(chosen) == 1 and chosen[0].red_team.verdict in ("pass", "veto")
    assert all(0 < p.hypothesis.expected_ratio <= 1.5 for p in a.proposals)
