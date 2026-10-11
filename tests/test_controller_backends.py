import pytest

from app.controller.gamepad_backend import XInputGamepadController
from app.controller.keyboard_backend import KeyboardController


def test_keyboard_backend_raises_clearly_when_dependency_missing():
    # The 'keyboard' package is not installed in this environment; the
    # backend must fail loudly rather than silently pretending to work.
    with pytest.raises(RuntimeError, match="keyboard"):
        KeyboardController()


def test_gamepad_backend_raises_clearly_when_dependency_missing():
    with pytest.raises(RuntimeError, match="vgamepad"):
        XInputGamepadController()
