"""Camera detection and threaded capture (spec sections 2, 24, 25, 34, 35, 80, 81).

Runs capture on its own thread so the UI thread never blocks on cv2.VideoCapture.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

log = logging.getLogger("airwheel.camera")

MAX_PROBE_INDEX = 8


@dataclass(frozen=True)
class CameraInfo:
    index: int
    width: int
    height: int


def list_cameras(max_index: int = MAX_PROBE_INDEX) -> list[CameraInfo]:
    """Probe camera indices 0..max_index. Slow (opens each device briefly) -
    call once at startup / on demand, not every frame."""
    found: list[CameraInfo] = []
    for i in range(max_index + 1):
        cap = cv2.VideoCapture(i)
        try:
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
                found.append(CameraInfo(index=i, width=w, height=h))
        finally:
            cap.release()
    return found


class CameraStream:
    """Background thread that continuously grabs frames and keeps only the
    latest one available via get_latest_frame(), so processing never lags
    behind on a backlog of stale frames."""

    def __init__(self, device_index: int = 0, width: int = 1280, height: int = 720, fps: int = 30):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps_target = fps

        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._latest_ts_ms: int = 0
        self._connected = False
        self._measured_fps = 0.0
        self._frame_count = 0
        self._fps_window_start = time.monotonic()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def measured_fps(self) -> float:
        return self._measured_fps

    def start(self) -> bool:
        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            log.error("Camera %s could not be opened", self.device_index)
            self._connected = False
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps_target)
        self._connected = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="CameraStream")
        self._thread.start()
        log.info("Camera %s started", self.device_index)
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if self._cap is None:
                break
            ok, frame = self._cap.read()
            if not ok:
                log.warning("Camera %s read failed; marking disconnected", self.device_index)
                self._connected = False
                break
            now_ms = int(time.monotonic() * 1000)
            with self._lock:
                self._latest_frame = frame
                self._latest_ts_ms = now_ms
            self._update_fps()

    def _update_fps(self) -> None:
        self._frame_count += 1
        elapsed = time.monotonic() - self._fps_window_start
        if elapsed >= 1.0:
            self._measured_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_window_start = time.monotonic()

    def get_latest_frame(self) -> tuple[np.ndarray | None, int]:
        """Returns (BGR frame copy, timestamp_ms) or (None, 0) if nothing yet."""
        with self._lock:
            if self._latest_frame is None:
                return None, 0
            return self._latest_frame.copy(), self._latest_ts_ms

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._connected = False
        log.info("Camera %s stopped", self.device_index)

    def __enter__(self) -> "CameraStream":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()


def to_rgb(frame_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def mirror(frame: np.ndarray) -> np.ndarray:
    return cv2.flip(frame, 1)
