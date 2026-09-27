"""Synthetic timestamp replays exercise compression; Windows tests use the real reader."""
import sys
import time

import pytest

from core.contracts import Settings
from core.sensing.sampler import Sample, Sampler, SpanCompressor, WindowsReader, input_is_idle
from core.sensing.store import SpanStore

from .conftest import P, synthetic_span as span


def sample(seconds, mono=None, process="WINWORD.EXE", title="cap3", idle=False, locked=False):
    return Sample(P + int(seconds * 1000), seconds if mono is None else mono,
                  process, title, idle, locked)


def replay(samples, stop=None):
    compressor, rows = SpanCompressor(), {}
    for item in samples:
        for row in compressor.feed(item):
            rows[row.start_ms] = row
    if stop:
        for row in compressor.close(P + stop[0] * 1000, stop[1]):
            rows[row.start_ms] = row
    return list(rows.values())


def test_identical_samples_compress_and_stop_flushes_one_period():
    rows = replay([sample(0), sample(1), sample(2)], (3, 3))
    assert rows == [span(0, 3)]


@pytest.mark.parametrize("change", [dict(process="notepad.exe"), dict(title="tesis"),
                                    dict(idle=True), dict(locked=True)])
def test_any_state_change_starts_new_span(change):
    rows = replay([sample(0), sample(1), sample(2, **change), sample(3, **change)])
    assert len(rows) == 2
    assert rows[0].end_ms == rows[1].start_ms == P + 2000


def test_gap_over_five_seconds_is_not_compressed_as_work():
    rows = replay([sample(0), sample(1), sample(20), sample(21)], (22, 22))
    assert rows == [span(0, 2), span(20, 22)]


def test_exactly_five_seconds_is_continuous():
    assert replay([sample(0), sample(5)]) == [span(0, 5)]


def test_forward_wall_clock_jump_is_not_work():
    rows = replay([sample(0), sample(1), sample(3600, 2), sample(3601, 3)])
    assert rows == [span(0, 2), span(3600, 3601)]


def test_backward_clock_jump_never_produces_overlaps():
    rows = replay([sample(100, 0), sample(101, 1), sample(50, 2), sample(51, 3),
                   sample(102, 54), sample(103, 55)])
    assert rows == [span(100, 101), span(102, 103)]


def test_shutdown_after_suspend_does_not_fill_the_suspend():
    rows = replay([sample(0), sample(1)], (3600, 3600))
    assert rows == [span(0, 2)]


def test_idle_is_strictly_greater_than_120_seconds_and_wraps_dword():
    assert not input_is_idle(121000, 1000)
    assert input_is_idle(121001, 1000)
    assert not input_is_idle(20, 0xFFFFFFF0)
    assert input_is_idle(130000, 0xFFFFFFF0)


def test_retention_runs_at_start_daily_and_when_settings_change(tmp_path):
    settings = Settings(raw_retention_days=14)
    store = SpanStore(tmp_path / "activity.sqlite")
    sampler = Sampler(store, lambda: settings)
    day = 86400000
    try:
        store.write(span(0, 10))
        sampler.maintain(P + 15 * day, 0)
        assert store.spans(P, P + 10000) == []
        store.write(span(2 * 86400, 2 * 86400 + 10))
        sampler.maintain(P + 16 * day, 86400)
        assert len(store.spans(P, P + 3 * day)) == 1
        sampler.maintain(P + 17 * day, 2 * 86400)
        assert store.spans(P, P + 3 * day) == []
        store.write(span(16 * 86400, 16 * 86400 + 10))
        settings.raw_retention_days = 1
        sampler.maintain(P + 17 * day + 11000, 2 * 86400 + 11)
        assert store.spans(P, P + 18 * day) == []
    finally:
        store.close()


def test_privacy_pause_survives_a_sidecar_restart(tmp_path):
    path = tmp_path / "activity.sqlite"
    store = SpanStore(path)
    first = Sampler(store, Settings)
    first.pause(5)
    saved = first.paused_until_ms
    first.stop()
    store.close()
    reopened = SpanStore(path)
    second = Sampler(reopened, Settings)
    try:
        assert second.paused_until_ms == saved
        second.resume()
        assert Sampler(reopened, Settings).paused_until_ms is None
        reopened.set_metadata("paused_until_ms", 1)
        assert Sampler(reopened, Settings).paused_until_ms is None
        assert reopened.metadata("paused_until_ms") is None
    finally:
        reopened.close()


@pytest.mark.windows
@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop required")
def test_live_reader_has_bounded_fields_and_process_lookup_works():
    import os
    reader = WindowsReader()
    assert reader.process_name(os.getpid()).casefold() == "python.exe"
    assert reader.process_name(0xFFFFFFFF) == "?"
    process, title, idle, locked = reader.read()
    # Assertions only expose sizes and booleans, never the private title.
    assert len(process) <= 260 and len(title) <= 512
    assert type(idle) is bool and type(locked) is bool


@pytest.mark.windows
@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop required")
def test_live_sampler_lifecycle_and_privacy_pause(tmp_path):
    store = SpanStore(tmp_path / "activity.sqlite")
    sampler = Sampler(store, Settings)
    start = time.time_ns() // 1_000_000
    try:
        sampler.pause(1)
        sampler.start()
        sampler.start()
        time.sleep(1.2)
        assert sampler.running
        assert store.last_sample_ms() is not None
        sampler.stop()
        sampler.stop()
        rows = store.spans(start, time.time_ns() // 1_000_000)
        assert len(rows) > 0
        assert all(row.process == "__paused__" and row.title == "" and row.idle for row in rows)
        assert not sampler.running
        sampler.resume()
        assert sampler.paused_until_ms is None
    finally:
        sampler.stop()
        store.close()
