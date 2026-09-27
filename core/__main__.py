"""Arranque del núcleo: `python -m core --port 0 --data-dir <dir>`.

Protocolo con Electron (ver contracts/README.md): el token llega por la variable NDE1_TOKEN; el
núcleo escucha solo en 127.0.0.1 e imprime una línea `NDE1_READY {...}` con el puerto elegido.
"""
from __future__ import annotations

import argparse
import os
import secrets
import socket
import sys
from pathlib import Path

import uvicorn

from core.app import create_app, ready_line


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m core")
    ap.add_argument("--port", type=int, default=0, help="0 = puerto libre elegido por el sistema")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    args = ap.parse_args(argv)

    token = os.environ.get("NDE1_TOKEN")
    if not token:
        token = secrets.token_urlsafe(32)
        print(f"NDE1_TOKEN no definido; token de esta sesión: {token}", file=sys.stderr)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", args.port))
    sock.listen(128)                     # conexiones en cola desde ya: la línea READY no miente
    port = sock.getsockname()[1]
    app = create_app(args.data_dir, token)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    print(ready_line(port), flush=True)
    server.run(sockets=[sock])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
