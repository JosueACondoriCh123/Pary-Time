"""Optional real frozen-binary smoke test; run after building packaging/sidecar.spec."""
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import httpx
import pytest


EXE = os.environ.get("NDE1_SIDECAR_EXE")


@pytest.mark.windows
@pytest.mark.skipif(sys.platform != "win32" or not EXE, reason="set NDE1_SIDECAR_EXE to the built executable")
def test_frozen_sidecar_serves_activity_and_preserves_pause_after_restart(tmp_path):
    bundle = Path(EXE).resolve().parent
    for name in ("scout.md", "premortem.md"):
        assert (bundle / "_internal" / "core" / "council" / "prompts" / name).is_file()
    token = "sidecar-test-token"
    environment = {**os.environ, "NDE1_TOKEN": token}
    saved_pause = None
    for attempt in range(2):
        process = subprocess.Popen(
            [str(Path(EXE).resolve()), "--port", "0", "--data-dir", str(tmp_path)],
            env=environment, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        messages = queue.Queue()
        reader = threading.Thread(target=lambda: messages.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            line = messages.get(timeout=30).strip()
            assert line.startswith("NDE1_READY "), "frozen sidecar failed before READY"
            ready = json.loads(line.removeprefix("NDE1_READY "))
            with httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}", timeout=15,
                              headers={"X-NDE1-Token": token}) as client:
                assert client.get("/health").json()["ok"]
                summary = client.get("/activity/today")
                assert summary.status_code == 200
                if attempt == 0:
                    saved_pause = client.post("/activity/pause", params={"minutes": 5}).json()["paused_until_ms"]
                    assert saved_pause is not None
                else:
                    assert summary.json()["paused_until_ms"] == saved_pause
                    assert client.post("/activity/resume").json()["paused_until_ms"] is None
                assert client.get("/journal/verify").json()["ok"]
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            reader.join(timeout=1)
            process.stdout.close()
            process.stderr.close()
