"""Agregación pura del historial de uso ("Mi tiempo"). Mismo input, mismo output; sin reloj ni disco.

Cada tramo del sensor se parte por hora local y se clasifica:
  * `paused`      — pausa de privacidad (`__paused__`)
  * `idle`        — sin input o pantalla bloqueada
  * `work`        — dentro de la ventana de un bloque declarado [P, P + planned_minutes) y coincide con sus reglas
  * `distraction` — lo que `categorize` (Frente A) considera distracción
  * `other`       — el resto
Los títulos se usan solo para reconocer el patrón de distracción ("youtube"); la respuesta nunca los lleva.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Callable

from core.contracts import (ActivityHistory, ActivitySpan, AppUsage, Block, Category, DayUsage, HourUsage, Settings,
                            SiteUsage)
from core.interfaces import Categorize

CATEGORIES = ("work", "distraction", "other", "idle", "paused")
ACTIVE = ("work", "distraction", "other")
TOP_APPS = 15
SAME_APP_GAP_MS = 5_000
HOUR_MS = 3_600_000


def _day_start_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day).timestamp() * 1000)


def _classify(span: ActivitySpan, blocks: list[Block], settings: Settings, categorize: Categorize) -> str:
    if span.process == "__paused__":
        return "paused"
    if span.idle or span.locked:
        return "idle"
    for b in blocks:
        if b.planned_start_ms <= span.start_ms < b.planned_start_ms + b.planned_minutes * 60_000 \
                and categorize(span, b, settings) == Category.work:
            return "work"
    return "distraction" if categorize(span, None, settings) == Category.distraction else "other"


def _site(span: ActivitySpan, settings: Settings) -> str | None:
    title = span.title.lower()
    return next((p for p in settings.distraction_title_patterns if p.lower() in title), None)


def _hour_pieces(start: int, end: int):
    """(inicio, fin) partidos en cada cambio de hora local."""
    t = start
    while t < end:
        local = datetime.fromtimestamp(t / 1000).replace(minute=0, second=0, microsecond=0)
        nxt = min(end, int((local + timedelta(hours=1)).timestamp() * 1000))
        if nxt <= t:
            nxt = min(end, t + HOUR_MS)
        yield t, nxt
        t = nxt


def compute_history(spans: list[ActivitySpan], blocks_on: Callable[[str], list[Block]], settings: Settings,
                    categorize: Categorize, from_date: date, to_date: date, now_ms: int) -> ActivityHistory:
    lo = _day_start_ms(from_date)
    hi = min(_day_start_ms(to_date + timedelta(days=1)), now_ms)
    day_ms: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(CATEGORIES, 0))
    hour_ms: dict[int, dict[str, int]] = defaultdict(lambda: dict.fromkeys(CATEGORIES, 0))
    app_ms: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(CATEGORIES, 0))
    site_ms: dict[str, int] = defaultdict(int)
    blocks_cache: dict[str, list[Block]] = {}

    ordered = sorted((s for s in spans if s.end_ms > lo and s.start_ms < hi), key=lambda s: s.start_ms)
    runs: list[tuple[str, int, int]] = []            # (proceso, inicio, fin) de tramos activos contiguos
    for s in ordered:
        start, end = max(s.start_ms, lo), min(s.end_ms, hi)
        if end <= start:
            continue
        local_day = datetime.fromtimestamp(start / 1000).date().isoformat()
        if local_day not in blocks_cache:
            blocks_cache[local_day] = blocks_on(local_day) if blocks_on else []
        cat = _classify(s, blocks_cache[local_day], settings, categorize)
        for a, b in _hour_pieces(start, end):
            dt = datetime.fromtimestamp(a / 1000)
            day_ms[dt.date().isoformat()][cat] += b - a
            hour_ms[dt.hour][cat] += b - a
        if cat in ACTIVE:
            app_ms[s.process][cat] += end - start
            if cat == "distraction" and (site := _site(s, settings)):
                site_ms[site] += end - start
            if runs and runs[-1][0] == s.process and start - runs[-1][2] <= SAME_APP_GAP_MS:
                runs[-1] = (s.process, runs[-1][1], end)
            else:
                runs.append((s.process, start, end))

    to_min = lambda ms: int(ms // 60_000)                                   # noqa: E731
    days = []
    d = from_date
    while d <= to_date:
        cats = day_ms.get(d.isoformat(), dict.fromkeys(CATEGORIES, 0))
        days.append(DayUsage(local_date=d.isoformat(), minutes_by_category={k: to_min(v) for k, v in cats.items()},
                             active_minutes=to_min(sum(cats[k] for k in ACTIVE))))
        d += timedelta(days=1)
    totals_ms = {k: sum(v[k] for v in day_ms.values()) for k in CATEGORIES}
    active_ms = sum(totals_ms[k] for k in ACTIVE)
    apps = sorted(((p, sum(c[k] for k in ACTIVE), c) for p, c in app_ms.items()), key=lambda x: -x[1])[:TOP_APPS]
    switches = max(len(runs) - 1, 0)
    return ActivityHistory(
        from_date=from_date.isoformat(), to_date=to_date.isoformat(), days=days,
        hours=[HourUsage(hour=h, minutes_by_category={k: to_min(v) for k, v in
                                                     hour_ms.get(h, dict.fromkeys(CATEGORIES, 0)).items()})
               for h in range(24)],
        apps=[AppUsage(process=p[:260], minutes=to_min(total), share=round(total / active_ms, 4) if active_ms else 0.0,
                       category=max(ACTIVE, key=lambda k: cats[k])) for p, total, cats in apps if total >= 60_000],
        sites=[SiteUsage(site=k, minutes=to_min(v)) for k, v in sorted(site_ms.items(), key=lambda x: -x[1])
               if v >= 60_000],
        totals={k: to_min(v) for k, v in totals_ms.items()},
        active_minutes=to_min(active_ms),
        distraction_share=round(totals_ms["distraction"] / active_ms, 4) if active_ms else 0.0,
        work_share=round(totals_ms["work"] / active_ms, 4) if active_ms else 0.0,
        longest_focus_min=to_min(max((e - s for _, s, e in runs), default=0)),
        switches_per_hour=round(switches / (active_ms / HOUR_MS), 2) if active_ms >= HOUR_MS / 4 else 0.0,
        retention_days=settings.raw_retention_days, generated_ms=now_ms)
