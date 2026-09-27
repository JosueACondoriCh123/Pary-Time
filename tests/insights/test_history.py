"""Historial de uso ("Mi tiempo"): agregación con el categorize real de A y bloques reales. Datos SINTÉTICOS."""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from core.app import create_app
from core.contracts import ActivitySpan, Block, BlockStatus, Settings, Target, TaskKind, WorkMatcher
from core.insights.aggregate import compute_history
from core.sensing.categorize import categorize

DAY = date(2026, 9, 29)


def ms(h, m=0, d=DAY):
    return int(datetime(d.year, d.month, d.day, h, m).timestamp() * 1000)


def span(a, b, process, title="", idle=False):
    return ActivitySpan(start_ms=a, end_ms=b, process=process, title=title, idle=idle)


def block(start, minutes=60):
    return Block(block_id="blk_000000000001", local_date=DAY.isoformat(), planned_start_ms=start,
                 planned_minutes=minutes, task_kind=TaskKind.escritura, task_label="Tesis-privada",
                 target=Target(kind="none"), work_matchers=[WorkMatcher(field="process", pattern="WINWORD.EXE")],
                 status=BlockStatus.started, created_ms=start - 1)


SPANS = [
    span(ms(8, 30), ms(9, 10), "chrome.exe", "YouTube - Google Chrome"),       # 40 min distracción
    span(ms(9, 10), ms(10, 0), "WINWORD.EXE", "cap3-secreto.docx - Word"),      # 50 min trabajo (en el bloque)
    span(ms(10, 0), ms(10, 30), "WINWORD.EXE", "cap3-secreto.docx - Word"),     # 30 min fuera del bloque: otra
    span(ms(10, 30), ms(10, 45), "WINWORD.EXE", "", idle=True),                  # 15 min inactivo
    span(ms(10, 45), ms(11, 0), "__paused__", "", idle=True),                    # 15 min pausa
    span(ms(11, 0), ms(11, 20), "WhatsApp.exe", "WhatsApp"),                     # 20 min distracción
]


def history(spans=SPANS, blocks=None, a=DAY, b=DAY, now=None):
    blocks = [block(ms(9, 0))] if blocks is None else blocks
    return compute_history(spans, lambda d: blocks if d == DAY.isoformat() else [], Settings(), categorize, a, b,
                           now or ms(23, 0))


def test_categories_work_only_inside_declared_blocks():
    h = history()
    assert h.totals == {"work": 50, "distraction": 60, "other": 30, "idle": 15, "paused": 15}
    assert h.active_minutes == 140
    assert h.work_share == round(50 / 140, 4) and h.distraction_share == round(60 / 140, 4)


def test_hours_apps_sites_and_focus():
    h = history()
    by_hour = {x.hour: x.minutes_by_category for x in h.hours}
    assert by_hour[8]["distraction"] == 30 and by_hour[9]["distraction"] == 10 and by_hour[9]["work"] == 50
    apps = {a.process: a for a in h.apps}
    assert apps["WINWORD.EXE"].minutes == 80 and apps["WINWORD.EXE"].category == "work"
    assert apps["chrome.exe"].category == "distraction" and "__paused__" not in apps
    assert [(s.site, s.minutes) for s in h.sites] == [("youtube", 40), ("whatsapp", 20)]
    assert h.longest_focus_min == 80                                           # Word 9:10–10:30 sin cortar
    assert h.switches_per_hour == round(2 / (140 / 60), 2)                     # chrome → Word → WhatsApp


def test_days_cover_the_whole_range_and_cut_at_now():
    h = history(a=date(2026, 9, 28), b=DAY, now=ms(9, 40))
    assert [d.local_date for d in h.days] == ["2026-09-28", "2026-09-29"]
    assert h.days[0].active_minutes == 0
    assert h.totals["work"] == 30                                              # hasta las 9:40


def test_the_response_never_carries_window_titles_or_block_labels():
    text = history().model_dump_json()
    for secret in ("cap3-secreto", "Google Chrome", "Tesis-privada", "Word"):
        assert secret not in text


def test_route_validates_the_range_and_answers_empty_without_data(tmp_path):
    with TestClient(create_app(tmp_path, "tok")) as cl:
        h = {"X-NDE1-Token": "tok"}
        ok = cl.get("/activity/history", params={"from_date": "2026-09-20", "to_date": "2026-09-26"}, headers=h)
        assert ok.status_code == 200 and len(ok.json()["days"]) == 7 and ok.json()["retention_days"] == 14
        bad = cl.get("/activity/history", params={"from_date": "2026-09-26", "to_date": "2026-09-20"}, headers=h)
        assert bad.status_code == 422
        assert cl.get("/activity/history", params={"from_date": "2026-01-01", "to_date": "2026-09-20"},
                      headers=h).status_code == 422
        assert cl.get("/activity/history", params={"from_date": "2026-09-20", "to_date": "2026-09-26"}).status_code == 401
