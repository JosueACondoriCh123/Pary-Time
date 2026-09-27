import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.sensing.store import SpanStore

from .conftest import P, synthetic_span as span


def test_real_sqlite_roundtrip_clip_order_wal_and_reopen(tmp_path):
    path = tmp_path / "activity.sqlite"
    store = SpanStore(path)
    try:
        store.write(span(10, 30))
        store.write(span(0, 10, "chrome.exe", "youtube"))
        store.mark_sample(P + 30000)
        items = store.spans(P + 5000, P + 20000)
        assert [(s.start_ms - P, s.end_ms - P) for s in items] == [(5000, 10000), (10000, 20000)]
        assert store.spans(P, P) == []
        assert len(store.spans(P + 10000, P + 30000)) == 1
        with sqlite3.connect(path) as db:
            assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        store.close()
        assert store.last_sample_ms() == P + 30000
    finally:
        store.close()


def test_extensions_and_no_overlapping_rows(tmp_path):
    store = SpanStore(tmp_path / "activity.sqlite")
    try:
        store.write(span(0, 1))
        store.write(span(0, 2))
        assert len(store.spans(P, P + 10000)) == 1
        with pytest.raises(ValueError, match="overlap"):
            store.write(span(1, 3))
    finally:
        store.close()


@pytest.mark.parametrize("replacement", [span(0, 5), span(0, 20, "Discord.exe", ""),
                                          span(0, 20, idle=True), span(0, 20, title="tesis")])
def test_persisted_observations_cannot_be_shortened_or_reclassified(tmp_path, replacement):
    store = SpanStore(tmp_path / "activity.sqlite")
    try:
        original = span(0, 10)
        store.write(original)
        with pytest.raises(ValueError, match="may only be extended"):
            store.write(replacement)
        assert store.spans(P, P + 30000) == [original]
        assert store.latest_end_ms() == P + 10000
    finally:
        store.close()


def test_retention_clips_old_rows_and_does_not_resurrect_them(tmp_path):
    store = SpanStore(tmp_path / "activity.sqlite")
    try:
        store.write(span(0, 10))
        store.write(span(10, 30))
        assert store.prune(P + 20000) == 1
        store.write(span(0, 10))
        store.write(span(10, 40))
        items = store.spans(P, P + 50000)
        assert [(s.start_ms - P, s.end_ms - P) for s in items] == [(20000, 40000)]
    finally:
        store.close()


def test_concurrent_reader_and_writer_use_real_sqlite(tmp_path):
    store = SpanStore(tmp_path / "activity.sqlite")
    def writer():
        for i in range(100):
            store.write(span(i, i + 1))
            store.mark_sample(P + i * 1000)
    def reader():
        for _ in range(100):
            items = store.spans(P, P + 100000)
            assert all(a.end_ms <= b.start_ms for a, b in zip(items, items[1:]))
    try:
        with ThreadPoolExecutor(3) as pool:
            futures = [pool.submit(writer), pool.submit(reader), pool.submit(reader)]
            for future in futures:
                future.result()
        assert len(store.spans(P, P + 100000)) == 100
    finally:
        store.close()


def test_initialization_failure_releases_file_and_can_recover(tmp_path):
    path = tmp_path / "activity.sqlite"
    path.write_bytes(b"invalid SQLite synthetic canary")
    store = SpanStore(path)
    try:
        for _ in range(20):
            with pytest.raises(sqlite3.DatabaseError):
                store.latest_end_ms()
            assert store._db is None
        # Windows refuses unlink while sqlite connections retain the file handle.
        path.unlink()
        store.write(span(0, 1))
        assert store.latest_end_ms() == P + 1000
    finally:
        store.close()
