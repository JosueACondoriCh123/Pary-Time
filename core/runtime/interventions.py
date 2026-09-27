"""Intervenciones de B2: capa Win32 mínima + selección pura de ventanas de distracción.

Reglas (brief-b / constitución):
  * Se MINIMIZA (SW_MINIMIZE), nunca se oculta ni se cierra nada.
  * Nunca se toca un proceso de `whitelist_processes`, la propia app, el núcleo ni el escritorio.
  * Revertir restaura SOLO las ventanas que minimizamos, que siguen siendo del MISMO proceso (los hwnd se
    reciclan: sin ese chequeo se podría restaurar una ventana ajena) y que siguen minimizadas.
  * `abrir_trabajo` abre el objetivo y al revertir no hace nada: nunca se cierra el trabajo de la persona.

El filtro de ventanas reales (sin dueño, sin estilo de herramienta). Las cloaked se conservan y
`select_distractions` se queda solo con las que ya son distracción: WhatsApp UWP y un video a
pantalla completa siguen cloaked mientras se ven; el resto no se minimiza.
"""
from __future__ import annotations

import logging
import ntpath
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from core.contracts import ActivitySpan, Category, Settings, Target
from core.interfaces import Categorize

log = logging.getLogger(__name__)

# Nunca se minimizan: la propia app (empaquetada y en desarrollo), el núcleo y el escritorio de Windows.
PROTECTED_PROCESSES = frozenset({"pary time.exe", "consejo n-de-1.exe", "nde1-core.exe", "electron.exe", "explorer.exe"})


# El escritorio nuevo de WhatsApp no se llama WhatsApp.exe. ApplicationFrameHost es el marco UWP.
_WHATSAPP_PROCESSES = frozenset({"whatsapp.exe", "whatsapp.root.exe"})


@dataclass(frozen=True)
class WinInfo:
    """Ventana top-level visible. `title` es LOCAL: nunca va al journal ni a los logs.

    `cloaked` queda en el objeto porque WhatsApp UWP y un YouTube a pantalla completa pueden
    seguir cloaked mientras se ven. El filtro de más abajo decide si igual cuentan.
    """
    hwnd: int
    pid: int
    process: str
    title: str
    cloaked: bool = False


class WindowOps(Protocol):
    def windows(self) -> list[WinInfo]: ...
    def minimize(self, hwnd: int) -> bool: ...
    def restore(self, hwnd: int, pid: int) -> bool:
        """Restaura solo si la ventana existe, sigue siendo de `pid` y está minimizada."""
        ...
    def is_minimized(self, hwnd: int) -> bool: ...


def _is_distraction(window: WinInfo, settings: Settings, categorize: Categorize) -> bool:
    """Distracción según Frente A, más el WhatsApp de escritorio que no matchea `WhatsApp.exe`.

    No cambia `categorize` ni outcome@1: solo decide qué ventanas minimiza esta intervención.
    Una ventana cloaked entra únicamente si ya es distracción (UWP visible o video a pantalla
    completa). El resto de las cloaked —otro escritorio, una UWP suspendida— queda afuera.
    """
    name = window.process.casefold()
    if name in _WHATSAPP_PROCESSES:
        return True
    if name == "applicationframehost.exe" and "whatsapp" in window.title.casefold():
        return True
    span = ActivitySpan(start_ms=0, end_ms=0, process=window.process[:260], title=window.title[:512],
                        idle=False)
    return categorize(span, None, settings) == Category.distraction


def select_distractions(windows: list[WinInfo], settings: Settings, categorize: Categorize) -> list[WinInfo]:
    """Ventanas de distracción, fuera de la lista blanca y de lo protegido.

    Una ventana cloaked solo llega acá si `windows()` la vio. Entra si ya es distracción
    (WhatsApp UWP o un YouTube cloaked en pantalla completa). Una cloaked que no es
    distracción no pasa `_is_distraction`.
    """
    white = {item.casefold() for item in settings.whitelist_processes}
    protected = PROTECTED_PROCESSES | white
    me = os.getpid()
    out = []
    for window in windows:
        name = window.process.casefold()
        if name in protected or window.pid == me:
            continue
        if name.startswith("whatsapp") and any(item.startswith("whatsapp") for item in white):
            continue
        if (name == "applicationframehost.exe" and "whatsapp" in window.title.casefold()
                and any(item.startswith("whatsapp") for item in white)):
            continue
        if _is_distraction(window, settings, categorize):
            out.append(window)
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


def no_desktop() -> bool:
    """NDE1_NO_DESKTOP=1 (lo fija la suite de tests): no tocar ventanas ni abrir archivos reales."""
    return os.environ.get("NDE1_NO_DESKTOP") == "1"


def _startfile(value: str) -> None:
    if no_desktop():
        raise OSError("NDE1_NO_DESKTOP: no se abren archivos reales")
    os.startfile(value)          # archivo, app o URL con la app predeterminada de Windows


# ---------------------------------------------------------------- Win32

_GW_OWNER, _GWL_EXSTYLE, _WS_EX_TOOLWINDOW, _DWMWA_CLOAKED = 4, -20, 0x00000080, 14


class Win32Ops:
    """Lo que se ve en la barra de tareas: ventanas top-level visibles, sin dueño, que no son de herramientas.
    Las cloaked se listan igual (con la marca) porque UWP y la pantalla completa las usan estando a la vista.
    Solo minimizar/restaurar."""

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Win32Ops solo funciona en Windows")
        import ctypes
        import win32con
        import win32gui
        import win32process
        self._ctypes, self._con, self._gui, self._proc = ctypes, win32con, win32gui, win32process

    def _process_name(self, pid: int) -> str:
        ctypes = self._ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return "?"
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(len(buf))
            return ntpath.basename(buf.value) if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else "?"
        finally:
            k32.CloseHandle(h)

    def _cloaked(self, hwnd: int) -> bool:
        ctypes = self._ctypes
        value = ctypes.c_int(0)
        try:
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, _DWMWA_CLOAKED, ctypes.byref(value),
                                                       ctypes.sizeof(value))
        except Exception:
            return False
        return value.value != 0

    def windows(self) -> list[WinInfo]:
        found: list[WinInfo] = []

        def visit(hwnd, _):
            try:
                gui = self._gui
                if not gui.IsWindowVisible(hwnd) or gui.GetWindow(hwnd, _GW_OWNER):
                    return True
                if gui.GetWindowLong(hwnd, _GWL_EXSTYLE) & _WS_EX_TOOLWINDOW:
                    return True
                title = gui.GetWindowText(hwnd)
                if title:
                    _, pid = self._proc.GetWindowThreadProcessId(hwnd)
                    found.append(WinInfo(hwnd, pid, self._process_name(pid), title[:512],
                                         cloaked=self._cloaked(hwnd)))
            except Exception as exc:                     # una ventana que se cierra durante el recorrido
                log.debug("ventana ignorada: %s", type(exc).__name__)
            return True

        self._gui.EnumWindows(visit, None)
        return found

    def pid_of(self, hwnd: int) -> int | None:
        if not self._gui.IsWindow(hwnd):
            return None
        try:
            return self._proc.GetWindowThreadProcessId(hwnd)[1]
        except Exception:
            return None

    def minimize(self, hwnd: int) -> bool:
        if not self._gui.IsWindow(hwnd) or self.is_minimized(hwnd):
            return False
        self._gui.ShowWindow(hwnd, self._con.SW_MINIMIZE)
        return True

    def restore(self, hwnd: int, pid: int) -> bool:
        if self.pid_of(hwnd) != pid or not self.is_minimized(hwnd):
            return False                                  # otro proceso (hwnd reciclado), cerrada o ya abierta
        self._gui.ShowWindow(hwnd, self._con.SW_RESTORE)
        return True

    def is_minimized(self, hwnd: int) -> bool:
        return bool(self._gui.IsWindow(hwnd) and self._gui.IsIconic(hwnd))


class NoWindows:
    """Sin ventanas que tocar (fuera de Windows o en pruebas de lógica). No es un mock: no finge
    comportamiento, simplemente no hay escritorio."""

    def windows(self) -> list[WinInfo]:
        return []

    def minimize(self, hwnd: int) -> bool:
        return False

    def restore(self, hwnd: int, pid: int) -> bool:
        return False

    def is_minimized(self, hwnd: int) -> bool:
        return False


def default_window_ops() -> WindowOps:
    if no_desktop():
        return NoWindows()
    try:
        return Win32Ops()
    except Exception as e:                                   # sin pywin32 o fuera de Windows
        log.warning("sin acceso a ventanas (%s): retrasar_distracciones no podrá minimizar", type(e).__name__)
        return NoWindows()
