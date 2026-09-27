"""Log del runtime para un soak largo. Las rutas de la persona no quedan en el archivo."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PATH = re.compile(r"[A-Za-z]:\\[^\s\"']+|/(?:Users|home)/[^\s\"']+")
_LOGGER = "core.runtime"


def redact(text: str) -> str:
    return _PATH.sub("[ruta]", text)


class PrivacyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def attach_runtime_log(data_dir: Path) -> logging.Handler:
    """Archivo rotativo en el data dir. Tres copias de 1 MB: un soak de 48 h no llena el disco."""
    data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(data_dir / "runtime.log", maxBytes=1_048_576, backupCount=3, encoding="utf-8")
    handler.setFormatter(PrivacyFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.setLevel(logging.INFO)
    logging.getLogger(_LOGGER).addHandler(handler)
    return handler


def detach_runtime_log(handler: logging.Handler | None) -> None:
    if handler is None:
        return
    logging.getLogger(_LOGGER).removeHandler(handler)
    handler.close()
