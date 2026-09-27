from core.contracts import Hypothesis, Moderator
from core.council.journal_view import JournalView
from core.council.snapshot import build_snapshot
from core.council.verifier import verify


def hyp(rationale, ids=(), ratio=0.6):
    return Hypothesis(intervention="retrasar_distracciones", moderator=Moderator(kind="time_of_day", value="morning"),
                      expected_ratio=ratio, rationale=rationale, cited_block_ids=list(ids))


def test_snapshot_is_aggregated_reproducible_and_carries_no_user_text(baseline):
    a = build_snapshot(JournalView.load(baseline))
    b = build_snapshot(JournalView.load(baseline))
    assert a.sha256 == b.sha256 and a.data["n_blocks"] == 24
    text = a.to_prompt()
    for banned in ("title", "task_label", "first_step", "WINWORD", ".docx"):
        assert banned not in text
    assert set(a.data["facts"]["by_time_of_day"]) == {"morning", "afternoon"}


def test_verifier_accepts_numbers_from_facts_and_rejects_invented_ones(baseline):
    snap = build_snapshot(JournalView.load(baseline))
    m = snap.data["facts"]["by_time_of_day"]["morning"]
    ok = hyp(f"En {m['n']} bloques de mañana la mediana fue {m['median_latency_min']} min y "
             f"{m['pct_first_is_distraction']}% arrancó en distracción; se espera 40% menos.",
             ids=[snap.rows[0]["block_id"]])
    assert verify(ok, snap).passed, verify(ok, snap).detail
    bad = hyp("La mediana de mañana fue 73.4 min, el triple que a la tarde.", ids=[snap.rows[0]["block_id"]])
    v = verify(bad, snap)
    assert not v.passed and "73.4" in v.detail


def test_verifier_rejects_unknown_block_ids_and_ignores_dates(baseline):
    snap = build_snapshot(JournalView.load(baseline))
    v = verify(hyp("Desde 2026-09-14 a las 09:00 hay retrasos.", ids=["blk_ffffffffffff"]), snap)
    assert not v.passed and "inexistentes" in v.detail and "2026" not in v.detail


def test_prompt_size_is_capped_whatever_the_baseline_length(journal):
    """Ollama trae 4096 tokens de contexto. Medido: 40 días → 2242 tokens de prompt con el system (~2 caracteres
    por token en esta tabla). Tope de 4000 caracteres para el snapshot + 1500 de salida del Scout = margen."""
    from tests.council.conftest import fill_baseline
    fill_baseline(journal, days=60)
    snap = build_snapshot(JournalView.load(journal))
    assert snap.data["n_blocks"] == 120 and len(snap.to_prompt()) <= 4000


def test_a_percentage_must_be_a_percentage_of_the_snapshot_not_any_number(baseline):
    """Caso real de qwen3.5:4b: "50% de escritura censurados" pasaba porque el 50 existía en otro lado."""
    snap = build_snapshot(JournalView.load(baseline))
    from core.council.verifier import allowed_numbers
    pool = allowed_numbers(snap, hyp("x"))["pct_censored"]
    # un conteo del snapshot que no está a menos de 1 punto de ningún % de censura (ni de su complemento)
    counts = sorted({f["n"] for g in snap.data["facts"].values() if isinstance(g, dict)
                     for f in ([g] if "n" in g else g.values())})
    count = next(c for c in counts if all(abs(c - v) > 1 for v in pool))
    v = verify(hyp(f"El {count}% de los bloques se censuró."), snap)
    assert not v.passed and f"{count}%" in v.detail
    assert verify(hyp(f"Hubo {count} bloques en ese grupo."), snap).passed


def test_minutes_must_be_latencies_or_minutes_of_the_snapshot(baseline):
    snap = build_snapshot(JournalView.load(baseline))
    pct = snap.data["facts"]["by_time_of_day"]["morning"]["pct_first_is_distraction"]
    v = verify(hyp(f"La mediana de mañana fue {pct} min."), snap)
    assert not v.passed and "min" in v.detail


def test_a_percentage_is_bound_to_the_topic_its_clause_names(baseline):
    snap = build_snapshot(JournalView.load(baseline))
    f = snap.data["facts"]["by_time_of_day"]["morning"]
    distr, cens = f["pct_first_is_distraction"], f["pct_censored"]
    assert distr != cens
    ok = hyp(f"A la mañana, el {distr}% arranca en distracción y el {cens}% queda censurado.")
    assert verify(ok, snap).passed, verify(ok, snap).detail
    # Un % de distracción que no es ni un % censurado ni su complemento en ningún grupo, puesto como censura.
    from core.council.verifier import allowed_numbers
    pool = allowed_numbers(snap, hyp("x"))["pct_censored"]
    everywhere = allowed_numbers(snap, hyp("x"))["pct"]
    wrong = next((v for v in sorted(everywhere) if v not in pool), None) or         next(v for v in range(1, 100) if v not in pool)
    swapped = hyp(f"A la mañana, el {wrong}% de los bloques queda censurado.")
    v = verify(swapped, snap)
    assert not v.passed and f"{wrong}%" in v.detail


def test_equivalent_forms_of_real_numbers_are_not_inventions(baseline):
    """Casos reales de qwen3.5:4b (2026-09-27): fracción de un %, el complemento del % censurado y la regla de 15 min."""
    snap = build_snapshot(JournalView.load(baseline))
    f = snap.data["facts"]["by_time_of_day"]["morning"]
    frac = round(f["pct_first_is_distraction"] / 100, 2)
    comp = 100 - f["pct_censored"]
    ok = hyp(f"La primera ventana es distracción con fracción {frac}; el {comp}% de las mañanas no queda censurado. "
             "Bloquear apps hasta completar 15 min.")
    assert verify(ok, snap).passed, verify(ok, snap).detail


def test_a_percentage_rounded_differently_is_not_an_invention(baseline):
    """Caso real: el modelo calculó 8/13 = 61.5% y escribió 61; el snapshot guarda 62."""
    snap = build_snapshot(JournalView.load(baseline))
    pct = snap.data["facts"]["by_time_of_day"]["morning"]["pct_first_is_distraction"]
    assert verify(hyp(f"La primera ventana es distracción en el {pct - 1}% de las mañanas."), snap).passed
    assert not verify(hyp(f"La primera ventana es distracción en el {pct - 7}% de las mañanas."), snap).passed
