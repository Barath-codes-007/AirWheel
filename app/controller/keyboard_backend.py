"""Digital keyboard fallback (spec sections 15, 48).

Clearly NOT analog - only usable for games that accept keyboard steering.
Requires the 'keyboard' package (Windows) and typically admin privileges
to hook global key events; not installed in this dev sandbox, so this
backend raises a clear error if used without it rather than pretending
to work (spec section 58, no fake functionality).
"""
from __future__ import annotations

import logging

from .base import VirtualController

log = logging.getLogger("airwheel.controller.keyboard")

try:
    import keyboard as _keyboard_lib
    _KEYBOARD_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when 'keyboard' isn't installed
    _KEYBOARD_AVAILABLE = False


class KeyboardController(VirtualController):
    """Digital-only fallback. Never holds LEFT and RIGHT simultaneously."""

    def __init__(self, left_key: str = "left", right_key: str = "right", threshold: float = 0.3):
        if not _KEYBOARD_AVAILABLE:
            raise RuntimeError(
                "The 'keyboard' package is not installed (Windows-only, needs "
                "admin privileges to hook global keys). Run: pip install keyboard"
            )
        self.left_key = left_key
        self.right_key = right_key
        self.threshold = threshold
        self._connected = False
        self._left_down = False
        self._right_down = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self.release_steering()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_left(self) -> None:
        if not self._left_down:
            _keyboard_lib.press(self.left_key)
            self._left_down = True
        if self._right_down:
            _keyboard_lib.release(self.right_key)
            self._right_down = False

    def set_right(self) -> None:
        if not self._right_down:
            _keyboard_lib.press(self.right_key)
            self._right_down = True
        if self._left_down:
            _keyboard_lib.release(self.left_key)
            self._left_down = False

    def release_steering(self) -> None:
        if self._left_down:
            _keyboard_lib.release(self.left_key)
            self._left_down = False
        if self._right_down:
            _keyboard_lib.release(self.right_key)
            self._right_down = False

    def set_steering(self, value: float) -> None:
        if value <= -self.threshold:
            self.set_left()
        elif value >= self.threshold:
            self.set_right()
        else:
            self.release_steering()

    def center(self) -> None:
        self.release_steering()

    def emergency_stop(self) -> None:
        self.release_steering()

    def stop(self) -> None:
        self.emergency_stop()
        self.disconnect()
