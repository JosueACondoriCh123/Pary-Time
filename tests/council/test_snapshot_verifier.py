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
