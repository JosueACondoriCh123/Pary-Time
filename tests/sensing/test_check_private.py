"""Privacy checks use real temporary Git repositories, never personal fixtures."""
import json
from pathlib import Path
import subprocess

import pytest

from scripts.check_private import (Allow, forbidden_file, load_allowlist, main,
                                   scan_history, scan_line, scan_worktree)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True).stdout


def write(root, path, text):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")


def commit(root, message):
    git(root, "add", ".")
    git(root, "-c", "user.name=Synthetic Test", "-c", "user.email=scanner" + "@example.org",
        "commit", "-qm", message)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    return tmp_path


def test_patterns_are_detected_without_exposing_values(repo, capsys):
    email = "synthetic-person" + "@example.org"
    secret = "sk" + "-" + "fakePrivateValue123456"
    winpath = "C:" + "\\Users\\synthetic-person\\Documents\\note"
    token_text = "token" + "=syntheticPrivateToken"
    write(repo, "fixture.txt", "\n".join([email, secret, winpath, token_text]))
    write(repo, "empty-allow.txt", "# intentionally empty\n")
    git(repo, "add", ".")
    assert main(["--root", str(repo), "--allowlist", str(repo / "empty-allow.txt")]) == 1
    output = capsys.readouterr().out
    assert all(value not in output for value in [email, secret, winpath, token_text])
    assert all(rule in output for rule in ["email", "key", "user-path", "token"])


def test_docs_paths_warn_but_data_and_json_escaped_paths_fail():
    private_path = "C:" + "\\Users\\synthetic-person\\file"
    assert scan_line("docs/brief.md", private_path, 1, [])[0].severity == "WARN"
    assert scan_line("data/fixture.json", json.dumps(private_path), 1, [])[0].severity == "ERROR"
    assert scan_line("fixture.txt", "/home/" + "synthetic-person/file", 1, [])[0].rule == "user-path"
    assert scan_line("readme.md", "Contact person" + "@example.org.", 1, [])[0].rule == "email"


@pytest.mark.parametrize("path", ["data/demo.raw.jsonl", "data/capture.sqlite-wal",
    "demo/journal.jsonl", "demo/journal.jsonl.bak", ".env", "config/.env.local", "data/owner.lock"])
def test_private_file_names_block_publication_even_if_empty(path):
    assert forbidden_file(path)
    assert not forbidden_file("docs/journal-events.md")


def test_trace_titles_need_exact_scoped_allowlist():
    path = "tests/fixtures/traces/demo.synthetic.jsonl"
    allow = [Allow("trace-title", path, "generic demo")]
    assert not scan_line(path, '{"title":"generic demo"}', 1, allow)
    assert not scan_line(path, '{"title":""}', 1, allow)
    assert scan_line(path, '{"title":"generic demo private"}', 1, allow)[0].rule == "trace-title"
    assert scan_line(path.replace("demo.", "other."), '{"title":"generic demo"}', 1, allow)
    assert scan_line(path, "broken json", 1, allow)[0].rule == "trace-invalid"
    assert scan_line(path, '{"title":42}', 1, allow)[0].rule == "trace-invalid"


def test_untracked_raw_ignored_but_tracked_empty_raw_is_found(repo):
    write(repo, "safe.md", "public text")
    git(repo, "add", "safe.md")
    write(repo, "private.raw.jsonl", "")
    findings, count = scan_worktree(repo, [])
    assert findings == [] and count == 1
    git(repo, "add", "private.raw.jsonl")
    findings, count = scan_worktree(repo, [])
    assert count == 2 and any(f.rule == "forbidden-file" for f in findings)


def test_history_finds_deleted_secrets_and_binary_files_without_author_email(repo):
    secret = "ghp" + "_" + "syntheticOnlyNeverValid"
    write(repo, "old file.txt", secret)
    (repo / "private.sqlite").write_bytes(b"\x00synthetic database")
    commit(repo, "synthetic initial fixture")
    git(repo, "rm", "old file.txt", "private.sqlite")
    commit(repo, "remove synthetic fixture")
    assert scan_worktree(repo, [])[0] == []
    findings = scan_history(repo, [])
    assert any(f.rule == "key" and f.path == "old file.txt" for f in findings)
    assert any(f.rule == "forbidden-file" and f.path == "private.sqlite" for f in findings)
    assert not any(f.rule == "email" for f in findings)  # metadata only
    assert all(f.commit for f in findings)


def test_history_also_reads_other_reachable_branches(repo):
    write(repo, "safe.md", "safe")
    commit(repo, "base")
    git(repo, "branch", "other")
    git(repo, "checkout", "-q", "other")
    write(repo, "note.txt", "hidden-person" + "@example.org")
    commit(repo, "synthetic email")
    git(repo, "checkout", "-q", "HEAD~1")
    assert any(f.rule == "email" for f in scan_history(repo, []))


def test_history_finds_secret_introduced_only_by_merge(repo):
    write(repo, "safe.md", "safe")
    commit(repo, "base")
    git(repo, "branch", "side")
    write(repo, "first.md", "first")
    commit(repo, "first parent")
    first = git(repo, "rev-parse", "HEAD").decode().strip()
    git(repo, "checkout", "-q", "side")
    write(repo, "second.md", "second")
    commit(repo, "second parent")
    git(repo, "-c", "user.name=Synthetic Test", "-c", "user.email=scanner" + "@example.org",
        "merge", "--no-commit", "--no-ff", first)
    write(repo, "merge-only.txt", "secret-person" + "@example.org")
    commit(repo, "merge-only synthetic email")
    merge = git(repo, "rev-parse", "HEAD").decode().strip()
    assert any(f.rule == "email" and f.commit == merge for f in scan_history(repo, []))


def test_private_filename_is_detected_but_redacted_in_output(repo, capsys):
    name = "private-person" + "@example.org"
    write(repo, name, "safe contents")
    write(repo, "allow.txt", "# none")
    git(repo, "add", ".")
    assert main(["--root", str(repo), "--allowlist", str(repo / "allow.txt")]) == 1
    output = capsys.readouterr().out
    assert "[redacted-path]" in output and name not in output


def test_allowlist_fails_closed_and_accepts_only_exact_values(tmp_path):
    file = tmp_path / "allow.txt"
    file.write_text("email|docs/*|person" + "@example.org|synthetic test\n", encoding="utf-8")
    entries = load_allowlist(file)
    assert not scan_line("docs/a.md", "person" + "@example.org", 1, entries)
    assert scan_line("data/a.md", "person" + "@example.org", 1, entries)
    file.write_text("unknown|*|anything|reason\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_allowlist(file)


def test_utf16_is_scanned_and_missing_tracked_file_is_error(repo):
    (repo / "wide.txt").write_text("person" + "@example.org", encoding="utf-16")
    commit(repo, "wide fixture")
    assert any(f.rule == "email" for f in scan_worktree(repo, [])[0])
    (repo / "wide.txt").unlink()
    assert scan_worktree(repo, [])[0][0].rule == "unread-file"


def test_missing_allowlist_returns_error_not_success(repo, capsys):
    assert main(["--root", str(repo), "--allowlist", str(repo / "missing.txt")]) == 2
    assert str(repo) not in capsys.readouterr().err
