"""Protocolo de arranque que usa Electron: NDE1_TOKEN por entorno, línea NDE1_READY por stdout."""
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def test_core_prints_ready_with_a_free_port_and_serves_health(tmp_path):
    env = {**os.environ, "NDE1_TOKEN": "tok-de-prueba"}
    p = subprocess.Popen([sys.executable, "-m", "core", "--port", "0", "--data-dir", str(tmp_path)],
                         cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        line = p.stdout.readline().strip()
        assert line.startswith("NDE1_READY "), line + p.stderr.read()
        info = json.loads(line.removeprefix("NDE1_READY "))
        base = f"http://127.0.0.1:{info['port']}"
        assert httpx.get(f"{base}/health", timeout=10).json()["ok"]
        r = httpx.get(f"{base}/settings", headers={"X-NDE1-Token": "tok-de-prueba"}, timeout=10)
        assert r.status_code == 200
    finally:
        p.terminate()
        p.wait(timeout=10)
