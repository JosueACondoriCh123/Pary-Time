"""Run A's checks and optionally build a tested Windows sidecar candidate.

Only receipts, the bundle manifest and candidate ZIP are intended for CI upload.
Detailed command logs stay local. This never tags, signs, pushes or publishes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_private import forbidden_file


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_state(root: Path) -> dict:
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, timeout=30).stdout.decode("utf-8").strip()
    return dict(commit=git("rev-parse", "HEAD"),
                dirty=bool(git("status", "--porcelain", "--untracked-files=normal")))


def run_step(name: str, command: list[str], root: Path, output: Path, env: dict,
             timeout_s: float = 1800) -> dict:
    started = time.monotonic()
    result = dict(name=name, passed=False, exit_code=None)
    try:
        with (output / f"{name}.log").open("wb") as log:
            process = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT, timeout=timeout_s)
        result.update(exit_code=process.returncode, passed=process.returncode == 0)
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    result["elapsed_s"] = round(time.monotonic() - started, 3)
    return result


def bundle_files(bundle: Path) -> list[dict]:
    def reject_link(path):
        attrs = path.lstat()
        if path.is_symlink() or getattr(attrs, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("bundle links are not permitted")
        return attrs
    reject_link(bundle)
    required = ("nde1-core.exe", "_internal/core/council/prompts/scout.md",
                "_internal/core/council/prompts/premortem.md")
    if not all((bundle / name).is_file() for name in required):
        raise ValueError("incomplete sidecar bundle")
    files = []
    pending = [bundle]
    while pending:
        for path in sorted(pending.pop().iterdir()):
            attrs = reject_link(path)  # Reject junctions before descending into them.
            name = path.relative_to(bundle).as_posix()
            if name != "nde1-core.exe" and name != "_internal" and not name.startswith("_internal/"):
                raise ValueError("unexpected bundle entry")
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                if forbidden_file(name):
                    raise ValueError("private data file in bundle")
                files.append(dict(path=name, bytes=attrs.st_size, sha256=digest(path)))
            else:
                raise ValueError("non-regular bundle entry")
    return sorted(files, key=lambda item: item["path"])


def package_bundle(bundle: Path, output: Path, source: dict) -> dict:
    files = bundle_files(bundle)
    manifest = dict(schema_version=1, artifact="nde1-core-windows-x64", source=source,
                    python=platform.python_version(), files=files)
    destination = output / "nde1-core-windows-x64.zip"
    manifest_path = output / "bundle-manifest.json"
    if destination.exists() or manifest_path.exists():
        raise FileExistsError("artifact destination already exists")
    payload = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    # A partial ZIP is never given the publishable candidate name.
    temporary = output / "bundle.zip.tmp"
    with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.write(bundle / item["path"], "nde1-core/" + item["path"])
        archive.writestr("bundle-manifest.json", payload)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise ValueError("candidate ZIP integrity failed")
        for item in files:
            with archive.open("nde1-core/" + item["path"]) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                    raise ValueError("bundle changed while packaging")
    temporary.replace(destination)
    manifest_path.write_text(payload, encoding="utf-8")
    checksum = digest(destination)
    (output / "SHA256SUMS.txt").write_text(f"{checksum}  {destination.name}\n", encoding="ascii")
    return dict(file=destination.name, sha256=checksum, bundled_files=len(files),
                bytes=destination.stat().st_size)


def run_ci(output: Path, *, build_sidecar: bool = False, history: bool = False) -> dict:
    if build_sidecar and (sys.platform != "win32" or sys.maxsize <= 2**32):
        raise ValueError("the sidecar candidate requires 64-bit Windows Python")
    output = output.resolve()
    if not output.is_relative_to(ROOT / "build"):
        raise ValueError("CI output must be a new directory under build")
    before = source_state(ROOT)
    if before["dirty"]:
        raise ValueError("commit the candidate sources before running CI")
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, NDE1_NO_DESKTOP="1", NDE1_LIVE_TESTS="0", PYTHONIOENCODING="utf-8")
    env.pop("NDE1_SIDECAR_EXE", None)
    report = dict(schema_version=1, check="frente_a_ci", source=before, checks_passed=False,
                  platform=sys.platform, python=platform.python_version(), steps=[], artifact=None,
                  release_approved=False)
    def step(name, *args):
        result = run_step(name, [sys.executable, *args], ROOT, output, env)
        report["steps"].append(result)
        print(json.dumps(result), flush=True)
        return result["passed"]
    try:
        checks = [("contracts", "tools/export_contracts.py", "--check"),
                  ("privacy", "scripts/check_private.py", *(["--history"] if history else [])),
                  ("sensing", "-m", "pytest", "tests/sensing", "-o", "addopts=", "-q"),
                  ("soak_smoke", "tools/capture/soak.py", "--out", str(output / "soak-smoke"),
                   "--seconds", "181")]
        for name, *args in checks:
            if not step(name, *args):
                return report
        if build_sidecar:
            report["pyinstaller"] = importlib.metadata.version("pyinstaller")
            if not step("build", "-m", "PyInstaller", "--noconfirm", "--clean", "--workpath",
                        str(output / "pyinstaller"), "--distpath", str(output / "dist"),
                        "packaging/sidecar.spec"):
                return report
            bundle = output / "dist" / "nde1-core"
            env["NDE1_SIDECAR_EXE"] = str(bundle / "nde1-core.exe")
            if not step("sidecar", "-m", "pytest", "tests/sensing/test_sidecar.py",
                        "-o", "addopts=", "-q"):
                return report
            if source_state(ROOT) != before:
                raise ValueError("sources changed during CI")
            report["artifact"] = package_bundle(bundle, output, before)
        if source_state(ROOT) != before:
            raise ValueError("sources changed during CI")
        report["checks_passed"] = True
    except Exception as exc:
        report["error_type"] = type(exc).__name__
    finally:
        (output / "ci-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--build-sidecar", action="store_true")
    parser.add_argument("--history", action="store_true", help="also scan all fetched Git history")
    args = parser.parse_args(argv)
    try:
        report = run_ci(args.out, build_sidecar=args.build_sidecar, history=args.history)
    except Exception as exc:
        print(json.dumps({"check": "frente_a_ci", "checks_passed": False,
                          "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(report))
    return 0 if report["checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
