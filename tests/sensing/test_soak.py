"""Real SQLite and elapsed-time tests; synthetic input never starts native capture."""
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from tools.capture.soak import BASE_MS, inspect_database, main, run_soak, synthetic_sample


def test_accelerated_run_is_labelled_and_does_not_claim_wall_clock_soak(tmp_path):
    output = tmp_path / "soak"
    result = run_soak(output, 181)
    assert result["status"] == "completed"
    assert result["checks_passed"]
    assert result["samples"] == 181
    assert result["logical_seconds"] == 181
    assert result["native_capture"] is False
    assert result["wall_48h_completed"] is False
    assert result["mode"] == "accelerated"
    assert result["issues"] == []
    assert result["rows"] == 6
    assert (output / "DATA_LABEL").read_text().strip() == "sintetico"
    assert json.loads((output / "status.json").read_text()) == result
    for name in ("status.json", "metrics.jsonl"):
        serialized = (output / name).read_text()
        assert "synthetic work" not in serialized
        assert "soak-work.exe" not in serialized
        assert str(tmp_path) not in serialized


def test_realtime_run_measures_actual_elapsed_time(tmp_path):
    result = run_soak(tmp_path / "realtime", 2, realtime=True)
    assert result["mode"] == "realtime"
    assert result["elapsed_wall_s"] >= 2
    assert result["checks_passed"]
    assert not result["wall_48h_completed"]


def test_existing_directory_is_never_reused_or_overwritten(tmp_path):
    marker = tmp_path / "DATA_LABEL"
    marker.write_text("real")
    with pytest.raises(FileExistsError):
        run_soak(tmp_path, 10)
    assert marker.read_text() == "real"
    assert list(tmp_path.iterdir()) == [marker]


@pytest.mark.parametrize("duration", [0, 1, -2, 14 * 86400 + 1, 3.5])
def test_invalid_duration_does_not_create_output(tmp_path, duration):
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        run_soak(output, duration)
    assert not output.exists()


def test_gap_and_clock_jump_schedule():
    assert synthetic_sample(3589) is not None
    assert all(synthetic_sample(s) is None for s in range(3590, 3600))
    assert synthetic_sample(3600).wall_ms == BASE_MS + 3600000
    assert synthetic_sample(7200).wall_ms == BASE_MS + 7320000
    assert synthetic_sample(10800).wall_ms == BASE_MS + 10800000
    assert synthetic_sample(10800).monotonic_s == 10800


def test_inspector_detects_overlap_expiry_and_unexpected_state_without_exporting_it(tmp_path):
    output = tmp_path / "soak"
    run_soak(output, 181)
    path = output / "activity.sqlite"
    with closing(sqlite3.connect(path)) as db:
        db.execute("INSERT INTO spans VALUES (?, ?, ?, ?, 0, 0)",
                   (BASE_MS + 1000, BASE_MS + 2000, "canary.exe", "private-canary"))
        db.commit()
    result = inspect_database(path, BASE_MS + 10000)
    assert result["integrity_ok"]
    assert result["overlaps"] == 1
    assert result["expired_spans"] == 2
    assert result["unexpected_states"] == 1
    assert "private-canary" not in json.dumps(result)


def test_cli_failure_omits_private_path(tmp_path, capsys):
    assert main(["--out", str(tmp_path), "--seconds", "10"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report == {"status": "failed", "error_type": "FileExistsError"}


def test_stop_request_closes_database_and_records_interruption(tmp_path):
    output = tmp_path / "stopped"
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(run_soak, output, 30, realtime=True)
        deadline = time.monotonic() + 10
        while not (output / "status.json").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (output / "status.json").exists()
        (output / "stop.request").touch()
        report = future.result(timeout=5)
    assert report["status"] == "interrupted"
    assert not report["checks_passed"]
    assert not report["wall_48h_completed"]
    assert report["integrity_ok"]
    # Windows requires all connections to have released the handle.
    (output / "activity.sqlite").unlink()
