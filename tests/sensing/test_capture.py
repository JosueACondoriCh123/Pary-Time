import json

import pytest

from core.contracts import Settings
from core.sensing.store import SpanStore
from tools.capture.record import export_raw
from tools.capture.sanitize import main, sanitize_file, sanitize_span

from .conftest import P, synthetic_span as span


def test_sanitizer_only_keeps_explicit_tokens_and_browser_patterns():
    settings = Settings()
    sanitized = sanitize_span(span(0, 10, "chrome.exe", "PERSONAL cap3 YouTube TESIS"),
                              ["cap3", "tesis"], settings)
    assert sanitized.title == "cap3 tesis youtube"
    assert sanitized.process == "chrome.exe"
    assert sanitize_span(span(0, 1, "notepad.exe", "youtube private"), [], settings).title == ""
    assert sanitize_span(span(0, 1, "__paused__", "cap3"), ["cap3"], settings).title == ""


def test_raw_sqlite_export_and_sanitized_fixture_roundtrip(tmp_path):
    store = SpanStore(tmp_path / "activity.sqlite")
    raw, clean = tmp_path / "session.raw.jsonl", tmp_path / "session.jsonl"
    try:
        store.write(span(0, 10, "WINWORD.EXE", "PRIVATE cap3 DOCUMENT"))
        assert export_raw(store, raw, P, P + 10000) == 1
        assert sanitize_file(raw, clean, ["cap3"], Settings()) == 1
        assert json.loads(clean.read_text()) == span(0, 10).model_dump()
        with pytest.raises(FileExistsError):
            sanitize_file(raw, clean, ["cap3"], Settings())
        with pytest.raises(ValueError):
            sanitize_file(raw, raw, [], Settings())
    finally:
        store.close()


def test_invalid_raw_input_does_not_leak_into_errors_or_partial_fixture(tmp_path, capsys):
    raw, clean = tmp_path / "session.raw.jsonl", tmp_path / "session.jsonl"
    raw.write_text('{"title":"PRIVATE_EXAMPLE"}', encoding="utf-8")
    assert main([str(raw), "--output", str(clean)]) == 1
    captured = capsys.readouterr()
    assert "PRIVATE_EXAMPLE" not in captured.err + captured.out
    assert not clean.exists()
