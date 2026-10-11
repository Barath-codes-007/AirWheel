"""AirWheel entry point.

Loads settings/logging, then tries to launch the PySide6 GUI. If PySide6 (or
a display) isn't available, falls back to a headless status printout rather
than crashing — this sandbox has neither, so headless mode is what's been
actually run and tested here. Camera capture, hand tracking, steering and
controller output are implemented (see app/camera, app/vision,
app/steering, app/controller, app/core/session.py) but wiring them into a
live camera+GUI loop has NOT been run end-to-end on real hardware yet.

Output is ALWAYS off at launch (spec sections 42 and 97).
"""
from __future__ import annotations

import logging
import sys

from app import __version__
from app.config import load_settings
from app.state import AppState
from app.utils.logging_setup import setup_logging


def run_headless(settings) -> int:
    log = logging.getLogger("airwheel")
    log.info("Running headless (no PySide6 / no display)")
    print(f"AirWheel {__version__} - headless mode")
    print(f"State: {AppState.IDLE.value} | input OFF | profile: {settings.active_profile}")
    print("GUI requires PySide6: pip install PySide6")
    print("Camera/tracking/steering/controller modules are implemented; "
          "see README for how to exercise them from Python directly.")
    return 0


def run_gui(settings) -> int:
    from PySide6.QtWidgets import QApplication

    from app.core.app_controller import AirWheelController
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow(settings)
    window.set_state(AppState.IDLE)
    # This controller is what actually connects START/STOP/CALIBRATE/
    # EMERGENCY to a real camera + hand tracker + steering session. It must
    # be kept alive for the app's lifetime (Qt does not own Python
    # references), hence attaching it to the window.
    controller = AirWheelController(window, settings)
    window._controller = controller
    window.show()
    return app.exec()


def main() -> int:
    settings = load_settings()
    setup_logging(settings.log_level)
    log = logging.getLogger("airwheel")
    log.info("AirWheel %s starting", __version__)

    try:
        import PySide6  # noqa: F401
    except ImportError:
        return run_headless(settings)

    try:
        return run_gui(settings)
    except Exception:
        log.exception("GUI failed to start; falling back to headless")
        return run_headless(settings)


if __name__ == "__main__":
    sys.exit(main())
