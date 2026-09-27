"""Intervenciones de B2: capa Win32 mínima + selección pura de ventanas de distracción.

Reglas (brief-b / constitución):
  * Se MINIMIZA (SW_MINIMIZE), nunca se oculta ni se cierra nada.
  * Nunca se toca un proceso de `whitelist_processes`.
  * Revertir restaura SOLO las ventanas que minimizamos y que siguen existiendo e iconificadas.
  * `abrir_trabajo` abre el objetivo y al revertir no hace nada: nunca se cierra el trabajo de la persona.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from core.contracts import ActivitySpan, Category, Settings, Target
from core.interfaces import Categorize

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WinInfo:
    hwnd: int
    process: str
    title: str


class WindowOps(Protocol):
    def windows(self) -> list[WinInfo]: ...
    def minimize(self, hwnd: int) -> bool: ...
    def restore(self, hwnd: int) -> bool: ...
    def exists(self, hwnd: int) -> bool: ...
    def is_minimized(self, hwnd: int) -> bool: ...


def select_distractions(windows: list[WinInfo], settings: Settings, categorize: Categorize) -> list[WinInfo]:
    """Ventanas que `categorize` (Frente A) considera distracción, fuera de la lista blanca."""
    white = {p.lower() for p in settings.whitelist_processes}
    out = []
    for w in windows:
        if w.process.lower() in white:
            continue
        span = ActivitySpan(start_ms=0, end_ms=0, process=w.process[:260], title=w.title[:512], idle=False)
        if categorize(span, None, settings) == Category.distraction:
            out.append(w)
    return out


# ---------------------------------------------------------------- abrir el trabajo

Opener = Callable[[str], None]


def open_target(target: Target, opener: Opener | None = None) -> str | None:
    """Abre el objetivo. Devuelve None si salió bien o el motivo del fallo (sin la ruta: va al log)."""
    if target.kind == "none" or not target.value.strip():
        return "el bloque no tiene objetivo"
    if target.kind == "file" and not Path(target.value).exists():
        return "el archivo objetivo no existe"
    try:
        (opener or _startfile)(target.value)
        return None
    except OSError as e:
        return f"no se pudo abrir el objetivo ({type(e).__name__})"


def _startfile(value: str) -> None:
    os.startfile(value)          # archivo, app o URL con la app predeterminada de Windows


# ---------------------------------------------------------------- Win32

class Win32Ops:
    """Ventanas top-level visibles con título. Solo lectura + minimizar/restaurar."""

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Win32Ops solo funciona en Windows")
        import ctypes
        import win32con
        import win32gui
        import win32process
        self._ctypes, self._con, self._gui, self._proc = ctypes, win32con, win32gui, win32process

    def _process_name(self, hwnd: int) -> str:
        ctypes = self._ctypes
        try:
            _, pid = self._proc.GetWindowThreadProcessId(hwnd)
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return "?"
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(len(buf))
                if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    return "?"
                return Path(buf.value).name
            finally:
                k32.CloseHandle(h)
        except Exception:                                    # proceso que murió entre medio, permisos
            return "?"

    def windows(self) -> list[WinInfo]:
        found: list[WinInfo] = []

        def cb(hwnd, _):
            if self._gui.IsWindowVisible(hwnd) and self._gui.GetWindowText(hwnd):
                found.append(WinInfo(hwnd, self._process_name(hwnd), self._gui.GetWindowText(hwnd)))
            return True

        self._gui.EnumWindows(cb, None)
        return found

    def minimize(self, hwnd: int) -> bool:
        if not self.exists(hwnd) or self.is_minimized(hwnd):
            return False
        self._gui.ShowWindow(hwnd, self._con.SW_MINIMIZE)
        return True

    def restore(self, hwnd: int) -> bool:
        if not self.exists(hwnd) or not self.is_minimized(hwnd):
            return False
        self._gui.ShowWindow(hwnd, self._con.SW_RESTORE)
        return True

    def exists(self, hwnd: int) -> bool:
        return bool(self._gui.IsWindow(hwnd))

    def is_minimized(self, hwnd: int) -> bool:
        return bool(self._gui.IsIconic(hwnd))


class NoWindows:
    """Sin ventanas que tocar (fuera de Windows o en pruebas de lógica). No es un mock: no finge
    comportamiento, simplemente no hay escritorio."""

    def windows(self) -> list[WinInfo]:
        return []

    def minimize(self, hwnd: int) -> bool:
        return False

    def restore(self, hwnd: int) -> bool:
        return False

    def exists(self, hwnd: int) -> bool:
        return False

    def is_minimized(self, hwnd: int) -> bool:
        return False


def default_window_ops() -> WindowOps:
    try:
        return Win32Ops()
    except Exception as e:                                   # sin pywin32 o fuera de Windows
        log.warning("sin acceso a ventanas (%s): retrasar_distracciones no podrá minimizar", type(e).__name__)
        return NoWindows()
