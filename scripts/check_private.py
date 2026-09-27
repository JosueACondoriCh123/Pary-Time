"""Read-only privacy gate for tracked working files and optional reachable Git patches.

Output contains locations and rule names, never matched contents. This is a pattern
check, not a review of images/media or proof that arbitrary prose is anonymous.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from fnmatch import fnmatchcase
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys


EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w-])")
USER_PATH = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+|/(?:Users|home)/)([^\\/\s\"'`<>]+)", re.I)
KEY = re.compile(r"(?<![\w-])(?:sk-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)")
TOKEN_PATTERN = re.compile(r"\btoken\s*=\s*(?:\"([^\"\r\n]+)\"|'([^'\r\n]+)'|([^\s\"'`&<>,;)]+))", re.I)
TRACE = "tests/fixtures/traces/"
ALLOW_RULES = {"email", "user-path", "key", "token", "trace-title"}
MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".mp4", ".webm", ".woff", ".woff2"}


@dataclass(frozen=True, order=True)
class Finding:
    severity: str
    path: str
    line: int
    rule: str
    commit: str = ""


@dataclass(frozen=True)
class Allow:
    rule: str
    path: str
    value: str


def load_allowlist(path: Path) -> list[Allow]:
    """rule|repository glob|exact allowed value|reason. No value regex/wildcards."""
    entries = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("|", 3)
        if len(fields) != 4 or fields[0] not in ALLOW_RULES or not all(fields):
            raise ValueError("invalid privacy allowlist entry")
        entries.append(Allow(*fields[:3]))
    return entries


def _allowed(entries: list[Allow], rule: str, path: str, value: str) -> bool:
    return any(e.rule == rule and fnmatchcase(path, e.path) and e.value == value for e in entries)


def forbidden_file(path: str) -> bool:
    p = PurePosixPath(path.lower())
    return (p.name.endswith(".raw.jsonl") or ".sqlite" in p.name
            or p.name == "journal.jsonl" or p.name.startswith("journal.jsonl.")
            or p.name == ".env" or p.name.startswith(".env.")
            or (path.lower().startswith("data/") and ".lock" in p.name))


def scan_line(path: str, line: str, number: int, allow: list[Allow],
              commit: str = "", *, check_trace: bool = True) -> list[Finding]:
    findings = []

    def add(rule: str, value: str, severity: str = "ERROR") -> None:
        if not _allowed(allow, rule, path, value):
            findings.append(Finding(severity, path, number, rule, commit))

    for match in EMAIL.finditer(line):
        add("email", match.group())
    for match in USER_PATH.finditer(line):
        add("user-path", match.group(1), "WARN" if path.startswith("docs/") else "ERROR")
    for match in KEY.finditer(line):
        add("key", match.group())
    for match in TOKEN_PATTERN.finditer(line):
        add("token", next(v for v in match.groups() if v is not None))
    if check_trace and path.startswith(TRACE) and path.endswith(".jsonl") and line.strip():
        try:
            row = json.loads(line)
            title = row["title"]
            if not isinstance(title, str):
                raise ValueError("title must be text")
            if title:
                add("trace-title", title)
        except (ValueError, KeyError, TypeError):
            findings.append(Finding("ERROR", path, number, "trace-invalid", commit))
    return findings


def _git(root: Path, *args: str) -> bytes:
    # Disable external diff/text converters: scanning must never execute repo hooks.
    return subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(root), *args],
                          check=True, capture_output=True).stdout


def scan_worktree(root: Path, allow: list[Allow]) -> tuple[list[Finding], int]:
    findings = []
    names = _git(root, "ls-files", "-z", "--cached").decode("utf-8").split("\0")
    paths = sorted(set(name for name in names if name))
    for name in paths:
        findings.extend(scan_line(name, name, 0, allow, check_trace=False))
        if forbidden_file(name):
            findings.append(Finding("ERROR", name, 0, "forbidden-file"))
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            findings.append(Finding("ERROR", name, 0, "unread-symlink"))
            continue
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(Finding("ERROR", name, 0, "unread-file"))
            continue
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            encoding = "utf-16"
        else:
            encoding = "utf-8-sig"
            if b"\0" in data or path.suffix.lower() in MEDIA:
                findings.append(Finding("WARN", name, 0, "binary-needs-review"))
                continue
        try:
            contents = data.decode(encoding)
        except UnicodeError:
            findings.append(Finding("ERROR", name, 0, "unread-encoding"))
            continue
        for number, line in enumerate(contents.splitlines(), 1):
            findings.extend(scan_line(name, line, number, allow))
    return findings, len(paths)


def scan_history(root: Path, allow: list[Allow]) -> list[Finding]:
    """Both added AND removed lines, all reachable refs; author metadata is omitted."""
    patch = _git(root, "log", "--all", "--full-history", "--format=PRIVATE_SCAN_COMMIT:%H",
                 "-p", "--diff-merges=first-parent", "--no-ext-diff", "--no-textconv", "--no-renames", "--unified=0",
                 "--src-prefix=a/", "--dst-prefix=b/", "--").decode("utf-8", errors="replace")
    findings = []
    commit = path = ""
    old = new = 0
    hunk = False
    for line in patch.splitlines():
        if line.startswith("PRIVATE_SCAN_COMMIT:"):
            commit = line.partition(":")[2]
            path = ""
            hunk = False
        elif line.startswith("diff --git "):
            hunk = False
            # Text paths below override this. The header also catches forbidden
            # binary files, whose patches have no ---/+++ headers.
            names = shlex.split(line[len("diff --git "):])
            path = names[1][2:] if len(names) == 2 else line.rsplit(" b/", 1)[-1]
            findings.extend(scan_line(path, path, 0, allow, commit, check_trace=False))
            if forbidden_file(path):
                findings.append(Finding("ERROR", path, 0, "forbidden-file", commit))
        elif not hunk and line.startswith(("--- ", "+++ ")):
            name = line[4:].split("\t", 1)[0]
            if name.startswith('"'):
                name = ast.literal_eval(name)
            if name.startswith(("a/", "b/")):
                path = name[2:]
        elif line.startswith("@@ "):
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match:
                old, new = map(int, match.groups())
                hunk = True
        elif hunk and path:
            if line.startswith("+"):
                findings.extend(scan_line(path, line[1:], new, allow, commit))
                new += 1
            elif line.startswith("-"):
                findings.extend(scan_line(path, line[1:], old, allow, commit))
                old += 1
            elif line.startswith(" "):
                old += 1
                new += 1
    return findings


def _safe_location(value: str) -> str:
    # A file name itself could contain an email or token. Never echo those either.
    if EMAIL.search(value) or KEY.search(value) or TOKEN_PATTERN.search(value) or USER_PATH.search(value):
        return "[redacted-path]"
    return value.encode("unicode_escape").decode("ascii")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--history", action="store_true", help="also scan patches of all reachable refs")
    parser.add_argument("--allowlist", type=Path, default=Path(__file__).with_name("check_private_allow.txt"))
    args = parser.parse_args(argv)
    try:
        root = Path(_git(args.root, "rev-parse", "--show-toplevel").decode("utf-8").strip())
        allow = load_allowlist(args.allowlist)
        findings, count = scan_worktree(root, allow)
        if args.history:
            findings.extend(scan_history(root, allow))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Privacy scan failed ({type(exc).__name__}); no file contents printed.", file=sys.stderr)
        return 2
    unique = sorted(set(findings))
    for item in unique:
        revision = f" commit={item.commit[:12]}" if item.commit else ""
        print(f"{item.severity} {_safe_location(item.path)}:{item.line} {item.rule}{revision}")
    errors = sum(f.severity == "ERROR" for f in unique)
    warnings = len(unique) - errors
    print(f"Scanned {count} tracked files; history={'yes' if args.history else 'no'}; "
          f"errors={errors}; warnings={warnings}. Untracked files and media contents are not audited.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
