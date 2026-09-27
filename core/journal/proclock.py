# Copiado de Night Council (night_council/proclock.py, mismo autor). Sin cambios de lógica.
"""Lock de proceso del loop: un solo escritor por diario.

Dos escritores sobre `data/journal.jsonl` romperían la cadena de hashes. El lock lo da el
**sistema operativo** sobre `data/loop.lock` (`msvcrt` en Windows, `flock` en Linux), no el
PID guardado en el archivo. Eso importa por tres razones:

  * el sistema libera el lock solo cuando el proceso muere, así que un lock abandonado
    queda libre al instante y no hay que adivinar si el dueño sigue vivo;
  * un PID reciclado tras un reinicio ya no puede dejar el lock trabado para siempre;
  * no hay ventana entre leer y escribir: dos arranques simultáneos no pueden ganar los dos.

El contenido del archivo ({"pid", "started"}) queda solo como pista para el watchdog.

Ojo en Windows: `os.kill(pid, 0)` NO sirve para consultar, termina el proceso. Se usa la API
de Windows (OpenProcess + GetExitCodeProcess).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_STILL_ACTIVE = 259
# Locks tomados en este proceso. Sin esta referencia, un `LoopLock(p).acquire()` cuyo objeto
# nadie guarda lo recolecta el intérprete, se cierra el archivo y el sistema SUELTA el candado.
_HELD: set = set()


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            return bool(ok) and code.value == _STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)                                  # POSIX: solo consulta
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class LoopLockError(RuntimeError):
    pass


def _try_lock(fh) -> bool:
    """Toma el lock exclusivo sin bloquear. False si ya lo tiene otro proceso."""
    if sys.platform == "win32":
        import msvcrt
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fh) -> None:
    if sys.platform == "win32":
        import msvcrt
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    import fcntl
    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LoopLock:
    def __init__(self, path: Path):
        self.path = Path(path)                              # datos del dueño, legibles siempre
        self.guard = self.path.with_name(self.path.name + ".guard")   # el candado del sistema
        self._fh = None

    def _write(self, data: dict) -> None:
        """Los datos del dueño van en un archivo aparte del candado: en Windows el lock es
        obligatorio y bloquearía la lectura del watchdog."""
        try:
            self.path.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass

    def holder(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return None

    def acquire(self) -> None:
        self.guard.parent.mkdir(parents=True, exist_ok=True)
        self.guard.touch(exist_ok=True)
        fh = self.guard.open("r+b")      # binario: en modo texto el seek no es un offset real
        if not _try_lock(fh):
            fh.close()
            h = self.holder() or {}
            raise LoopLockError(f"ya hay un escritor con el diario abierto "
                                f"(pid {h.get('pid', '?')}, desde {h.get('started', '?')})")
        self._fh = fh
        _HELD.add(self)
        self._write({"pid": os.getpid(), "started": _now()})

    def release(self) -> None:
        if self._fh is None:
            return
        self._write({"pid": None, "released": _now()})
        _unlock(self._fh)
        self._fh.close()
        self._fh = None
        _HELD.discard(self)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
