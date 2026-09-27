"""1 Hz Windows sampler and deterministic compression of timestamped observations.

Native imports are lazy so outcome analysis and contract export work without Windows.
Logs contain error classes only, never titles, executable paths or exception messages.
"""
from __future__ import annotations

import ctypes
import logging
import ntpath
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Callable

from core.contracts import OUTCOME_RULES, ActivitySpan, Settings

from .store import SpanStore

LOG = logging.getLogger(__name__)
SAMPLE_MS = 1000
MAX_GAP_S = 5
CLOCK_DRIFT_MS = 1000
ERROR_LOG_INTERVAL_S = 60


@dataclass(frozen=True)
class Sample:
    wall_ms: int
    monotonic_s: float
    process: str
    title: str
    idle: bool
    locked: bool = False

    @property
    def state(self) -> tuple[str, str, bool, bool]:
        return self.process, self.title, self.idle, self.locked


class SpanCompressor:
    """Each feed returns inserts/extensions for a store keyed by start_ms.

    A first sample has zero observed duration. Subsequent samples establish the
    interval. At shutdown or a gap, at most one sampling period is extrapolated.
    Clock jumps never manufacture long stretches of work. After a backward jump,
    observations are ignored until wall time catches up to the persisted end.
    """
    def __init__(self, not_before_ms: int | None = None):
        self._last: Sample | None = None
        self._current: ActivitySpan | None = None
        self._high_water = not_before_ms

    def feed(self, sample: Sample) -> list[ActivitySpan]:
        updates: list[ActivitySpan] = []
        if self._high_water is not None and sample.wall_ms < self._high_water:
            self._last = self._current = None
            return updates
        previous, current = self._last, self._current
        continuous = False
        if previous is not None and current is not None:
            elapsed = sample.monotonic_s - previous.monotonic_s
            wall_elapsed = sample.wall_ms - previous.wall_ms
            continuous = (0 <= elapsed <= MAX_GAP_S and wall_elapsed >= 0
                          and abs(wall_elapsed - elapsed * 1000) <= CLOCK_DRIFT_MS)
            end = sample.wall_ms if continuous else min(sample.wall_ms, previous.wall_ms + SAMPLE_MS)
            if end > current.start_ms:
                current = current.model_copy(update={"end_ms": end})
                updates.append(current)
                self._high_water = end
        if continuous and previous.state == sample.state:
            self._current = current
        else:
            self._current = ActivitySpan(start_ms=sample.wall_ms, end_ms=sample.wall_ms,
                                         process=sample.process, title=sample.title,
                                         idle=sample.idle, locked=sample.locked)
        self._last = sample
        # Also remember the first zero-duration observation for backward-clock detection.
        self._high_water = max(sample.wall_ms, self._high_water or sample.wall_ms)
        return updates

    def close(self, wall_ms: int, monotonic_s: float) -> list[ActivitySpan]:
        updates: list[ActivitySpan] = []
        if self._last is not None and self._current is not None:
            elapsed = monotonic_s - self._last.monotonic_s
            wall_elapsed = wall_ms - self._last.wall_ms
            if elapsed >= 0 and wall_elapsed >= 0 and abs(wall_elapsed - elapsed * 1000) <= CLOCK_DRIFT_MS:
                end = min(wall_ms, self._last.wall_ms + SAMPLE_MS)
                if end > self._current.start_ms:
                    updates.append(self._current.model_copy(update={"end_ms": end}))
                    self._high_water = end
        self._last = self._current = None
        return updates


def input_is_idle(ticks_ms: int, last_input_ms: int) -> bool:
    # GetLastInputInfo and GetTickCount use 32-bit DWORDs (wrap at ~49.7 days).
    return ((ticks_ms - last_input_ms) & 0xFFFFFFFF) > OUTCOME_RULES.idle_max_s * 1000


class WindowsReader:
    def __init__(self):
        if sys.platform != "win32":
            raise OSError("Windows activity sampling is unavailable on this platform")
        from ctypes import wintypes
        import win32api
        import win32gui
        import win32process

        self.api, self.gui, self.process = win32api, win32gui, win32process
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.user.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.user.OpenInputDesktop.restype = wintypes.HANDLE
        self.user.CloseDesktop.argtypes = [wintypes.HANDLE]
        self.user.CloseDesktop.restype = wintypes.BOOL

    def process_name(self, pid: int) -> str:
        from ctypes import wintypes
        handle = self.kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return "?"
        try:
            size = wintypes.DWORD(32768)
            name = ctypes.create_unicode_buffer(size.value)
            if not self.kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
                return "?"
            return ntpath.basename(name.value)[:260]
        finally:
            self.kernel.CloseHandle(handle)

    def read(self) -> tuple[str, str, bool, bool]:
        desktop = self.user.OpenInputDesktop(0, False, 0x0001)  # DESKTOP_READOBJECTS
        if not desktop:
            return "?", "", True, True
        self.user.CloseDesktop(desktop)
        hwnd = self.gui.GetForegroundWindow()
        # Read input first: a keystroke between the calls must not look like a DWORD wrap.
        last_input_ms = self.api.GetLastInputInfo()
        idle = input_is_idle(self.api.GetTickCount(), last_input_ms)
        if not hwnd:
            return "?", "", idle, False
        _, pid = self.process.GetWindowThreadProcessId(hwnd)
        process = self.process_name(pid)
        locked = process.casefold() == "lockapp.exe"
        title = "" if locked else self.gui.GetWindowText(hwnd)[:512]
        return process, title, idle, locked


class Sampler:
    def __init__(self, store: SpanStore, settings: Callable[[], Settings]):
        self.store, self.settings = store, settings
        self._reader: WindowsReader | None = None
        self._compressor: SpanCompressor | None = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._paused_until_ms: int | None = None
        self._pause_deadline: float | None = None
        self._pause_loaded = False
        self._retention_date: date | None = None
        self._retention_mono = 0.0
        self._retention_days: int | None = None
        self._last_ok_mono: float | None = None
        self._last_error_log_mono: float | None = None
        self._unreported_errors = 0

    @property
    def running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive() and self._last_ok_mono is not None
                        and time.monotonic() - self._last_ok_mono <= MAX_GAP_S)

    @property
    def paused_until_ms(self) -> int | None:
        with self._lock:
            self._restore_pause()
            if self._pause_deadline is not None and time.monotonic() >= self._pause_deadline:
                self._paused_until_ms = self._pause_deadline = None
                self.store.set_metadata("paused_until_ms", None)
            return self._paused_until_ms

    def _restore_pause(self) -> None:
        if not self._pause_loaded:
            saved = self.store.metadata("paused_until_ms")
            now_ms = time.time_ns() // 1_000_000
            if saved is not None and saved > now_ms:
                self._paused_until_ms = saved
                self._pause_deadline = time.monotonic() + (saved - now_ms) / 1000
            elif saved is not None:
                self.store.set_metadata("paused_until_ms", None)
            self._pause_loaded = True

    def _persist(self, spans: list[ActivitySpan]) -> None:
        for span in spans:
            self.store.write(span)

    def _ingest(self, sample: Sample) -> None:
        """Persist an observation; also used to replay recorded samples against real SQLite.

        Initialize lazily so building an app or exporting contracts opens no database.
        The previous process may have persisted times later than the current wall clock.
        """
        with self._lock:
            if self._compressor is None:
                self._compressor = SpanCompressor(not_before_ms=self.store.latest_end_ms())
            self._persist(self._compressor.feed(sample))
            self.store.mark_sample(sample.wall_ms)
            self._last_ok_mono = sample.monotonic_s

    def _close_span(self) -> None:
        if self._compressor is not None:
            self._persist(self._compressor.close(time.time_ns() // 1_000_000, time.monotonic()))

    def maintain(self, wall_ms: int, monotonic_s: float) -> None:
        today = date.fromtimestamp(wall_ms / 1000)
        days = self.settings().raw_retention_days
        if (today != self._retention_date or monotonic_s - self._retention_mono >= 86400
                or days != self._retention_days):
            self.store.prune(wall_ms - days * 86400 * 1000)
            self._retention_date, self._retention_mono, self._retention_days = today, monotonic_s, days

    def sample_once(self) -> None:
        with self._lock:
            wall_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
            self.maintain(wall_ms, mono)
            if self.paused_until_ms is not None:
                state = ("__paused__", "", True, False)
            else:
                if self._reader is None:
                    self._reader = WindowsReader()
                state = self._reader.read()
            sample = Sample(wall_ms, mono, *state)
            self._ingest(sample)

    def pause(self, minutes: int) -> None:
        if not 1 <= minutes <= 480:
            raise ValueError("pause must last 1 to 480 minutes")
        with self._lock:
            wall_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
            self._paused_until_ms = wall_ms + minutes * 60000
            self._pause_deadline = mono + minutes * 60
            self._pause_loaded = True
            self.store.set_metadata("paused_until_ms", self._paused_until_ms)
            self._ingest(Sample(wall_ms, mono, "__paused__", "", True))

    def resume(self) -> None:
        with self._lock:
            self._close_span()
            self._paused_until_ms = self._pause_deadline = None
            self._pause_loaded = True
            self.store.set_metadata("paused_until_ms", None)

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self.maintain(time.time_ns() // 1_000_000, time.monotonic())
            if sys.platform != "win32":
                LOG.warning("Activity sampler disabled: Windows is required")
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="nde1-sensor", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        next_tick = time.monotonic()
        while not self._stop.is_set():
            try:
                self.sample_once()
            except Exception as exc:
                self._report_error(exc, time.monotonic())
            next_tick += 1
            now = time.monotonic()
            if next_tick <= now:
                next_tick = now + 1
            self._stop.wait(next_tick - now)

    def _report_error(self, exc: Exception, monotonic_s: float) -> None:
        """Bound repeated failures without logging exception text or tracebacks.

        Count every failed tick, including intermittent failures. A successful tick
        does not reset the limit, so an alternating failure cannot flood stderr.
        """
        self._unreported_errors += 1
        if (self._last_error_log_mono is None
                or monotonic_s - self._last_error_log_mono >= ERROR_LOG_INTERVAL_S):
            LOG.warning("Activity samples skipped: %d (last error: %s)",
                        self._unreported_errors, type(exc).__name__)
            self._unreported_errors = 0
            self._last_error_log_mono = monotonic_s

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                raise RuntimeError("activity sampler did not stop")
        with self._lock:
            self._close_span()
            self._thread = None
