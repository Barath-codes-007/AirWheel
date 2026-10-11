"""Virtual XInput (Xbox 360) controller backend via vgamepad (spec sections
14, 49). Windows-only; requires the ViGEmBus driver.

    pip install vgamepad

installing the package also runs the ViGEmBus driver installer (accept the
license, click Install). Uninstall via Windows "Add or remove programs" ->
"ViGEmBus Driver" if you ever want to remove it.

vgamepad is not installed in this dev sandbox (it needs the Windows driver),
so this backend cannot be exercised here - it's implemented against the
library's documented API (github.com/yannbouteiller/vgamepad) but is
EXPERIMENTAL / UNTESTED until run on real Windows hardware. Verify against
the installed vgamepad version before relying on it.
"""
from __future__ import annotations

import logging

from .base import VirtualController

log = logging.getLogger("airwheel.controller.gamepad")

try:
    import vgamepad as vg
    _VGAMEPAD_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when vgamepad/driver isn't installed
    _VGAMEPAD_AVAILABLE = False


class XInputGamepadController(VirtualController):
    """EXPERIMENTAL - not yet run against real hardware. Steering maps to the
    left stick's X axis; throttle/brake map to the right/left triggers."""

    def __init__(self):
        if not _VGAMEPAD_AVAILABLE:
            raise RuntimeError(
                "vgamepad is not installed, or its ViGEmBus driver is missing "
                "(Windows only). Run: pip install vgamepad"
            )
        self._pad: "vg.VX360Gamepad | None" = None

    def connect(self) -> bool:
        try:
            self._pad = vg.VX360Gamepad()
            self._pad.reset()
            self._pad.update()
            log.info("Virtual XInput gamepad connected")
            return True
        except Exception as exc:  # noqa: BLE001 - surface any ViGEmBus/driver error
            log.error("Could not create virtual gamepad: %s", exc)
            self._pad = None
            return False

    def disconnect(self) -> None:
        if self._pad is not None:
            self.emergency_stop()
            self._pad = None

    @property
    def is_connected(self) -> bool:
        return self._pad is not None

    def set_steering(self, value: float) -> None:
        if self._pad is None:
            return
        v = max(-1.0, min(1.0, value))
        self._pad.left_joystick_float(x_value_float=v, y_value_float=0.0)
        self._pad.update()

    def set_throttle(self, value: float) -> None:
        if self._pad is None:
            return
        v = max(0.0, min(1.0, value))
        self._pad.right_trigger_float(value_float=v)
        self._pad.update()

    def set_brake(self, value: float) -> None:
        if self._pad is None:
            return
        v = max(0.0, min(1.0, value))
        self._pad.left_trigger_float(value_float=v)
        self._pad.update()

    def set_button(self, button: str, pressed: bool) -> None:
        if self._pad is None:
            return
        try:
            btn = getattr(vg.XUSB_BUTTON, button)
        except AttributeError:
            log.warning("Unknown gamepad button: %s", button)
            return
        if pressed:
            self._pad.press_button(button=btn)
        else:
            self._pad.release_button(button=btn)
        self._pad.update()

    def center(self) -> None:
        if self._pad is None:
            return
        self._pad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
        self._pad.right_trigger_float(value_float=0.0)
        self._pad.left_trigger_float(value_float=0.0)
        self._pad.update()

    def emergency_stop(self) -> None:
        if self._pad is None:
            return
        self._pad.reset()
        self._pad.update()
