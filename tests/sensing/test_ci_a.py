"""Real subprocesses and ZIP files; small invented bundle tests only the packer.

The real executable must also pass the separate frozen-sidecar smoke in ci_a.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from scripts.ci_a import bundle_files, digest, package_bundle, run_step, source_state


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "bundle"
    prompts = root / "_internal/core/council/prompts"
    prompts.mkdir(parents=True)
    (root / "nde1-core.exe").write_bytes(b"synthetic archive fixture, not an executable")
    (prompts / "scout.md").write_text("synthetic scout")
    (prompts / "premortem.md").write_text("synthetic premortem")
    return root


def test_bundle_is_complete_and_every_archived_byte_matches_manifest(bundle, tmp_path):
    receipt = package_bundle(bundle, tmp_path, {"commit": "a" * 40, "dirty": False})
    archive_path = tmp_path / receipt["file"]
    assert receipt["sha256"] == digest(archive_path)
    manifest = json.loads((tmp_path / "bundle-manifest.json").read_text())
    assert receipt["bundled_files"] == 3
    with zipfile.ZipFile(archive_path) as archive:
        assert json.loads(archive.read("bundle-manifest.json")) == manifest
        assert len(archive.namelist()) == 4
        for item in manifest["files"]:
            raw = archive.read("nde1-core/" + item["path"])
            assert len(raw) == item["bytes"]
            assert hashlib.sha256(raw).hexdigest() == item["sha256"]
    assert str(tmp_path) not in json.dumps(manifest)
    assert (tmp_path / "SHA256SUMS.txt").read_text().startswith(receipt["sha256"])
    with pytest.raises(FileExistsError):
        package_bundle(bundle, tmp_path, {})


@pytest.mark.parametrize("name", ["data.json", "_internal/journal.jsonl", "_internal/.env",
                                   "_internal/activity.sqlite", "_internal/trace.raw.jsonl"])
def test_private_or_unexpected_files_are_rejected_before_creating_zip(bundle, tmp_path, name):
    (bundle / name).write_text("synthetic private canary")
    with pytest.raises(ValueError):
        package_bundle(bundle, tmp_path, {})
    assert not (tmp_path / "nde1-core-windows-x64.zip").exists()


def test_missing_prompt_refuses_incomplete_bundle(bundle):
    (bundle / "_internal/core/council/prompts/scout.md").unlink()
    with pytest.raises(ValueError):
        bundle_files(bundle)


def test_bundle_link_is_rejected_without_reading_target(bundle, tmp_path):
    target = tmp_path / "private-target.txt"
    target.write_text("synthetic private target")
    link = bundle / "_internal" / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("OS does not allow this account to create symlinks")
    with pytest.raises(ValueError, match="links"):
        bundle_files(bundle)


def test_runner_propagates_failure_and_keeps_command_output_out_of_receipt(tmp_path):
    result = run_step("failure", [sys.executable, "-c", "print('private-canary'); raise SystemExit(7)"],
                      tmp_path, tmp_path, dict(os.environ))
    assert result["exit_code"] == 7 and not result["passed"]
    assert "private-canary" not in json.dumps(result)
    assert "private-canary" in (tmp_path / "failure.log").read_text()
    timeout = run_step("timeout", [sys.executable, "-c", "import time; time.sleep(10)"],
                       tmp_path, tmp_path, dict(os.environ), timeout_s=0.1)
    assert not timeout["passed"] and timeout["error_type"] == "TimeoutExpired"


def test_source_receipt_tracks_head_and_dirty_state_with_real_git(tmp_path):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)
    git("init")
    (tmp_path / "source.txt").write_text("synthetic source")
    git("add", "source.txt")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture" + "@example.invalid", "commit", "-m", "fixture")
    original = source_state(tmp_path)
    assert len(original["commit"]) == 40 and not original["dirty"]
    (tmp_path / "source.txt").write_text("synthetic change")
    changed = source_state(tmp_path)
    assert changed["dirty"] and changed["commit"] == original["commit"]
