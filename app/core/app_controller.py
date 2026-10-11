"""Wires the GUI (MainWindow) to camera capture, hand tracking, the steering
session and controller output. This is the piece that was MISSING before:
app/main.py created a MainWindow whose buttons emitted signals into empty
space - nothing was listening. This module is what actually listens.

Not run/tested here (no PySide6, no camera, no display in this dev
sandbox) - written against the documented PySide6 API and this project's
own already-tested modules, but genuinely unverified end-to-end. Please
report back exactly what happens (or doesn't) when you run it.
"""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QMessageBox

from app.camera.capture import CameraStream, mirror, to_rgb
from app.config.settings import AppSettings, save_settings
from app.controller.base import VirtualController
from app.controller.gamepad_backend import XInputGamepadController
from app.controller.keyboard_backend import KeyboardController
from app.core.session import SteeringSession
from app.profiles.manager import GameProfile, ProfileManager
from app.state import AppState
from app.steering.calibration import MIN_SAMPLES, CalibrationSample, compute_calibration
from app.steering.engine import SteeringConfig, SteeringEngine
from app.steering.pedals import PedalEngine
from app.ui.frame_convert import bgr_to_pixmap
from app.vision.geometry import Point, hand_separation, two_hand_angle_deg
from app.vision.gestures import classify_hand_pose
from app.vision.hand_tracking import DEFAULT_MODEL_PATH, HandTracker, split_left_right, wrist_point

log = logging.getLogger("airwheel.app_controller")

MIN_HAND_CONFIDENCE = 0.5
CALIBRATION_HOLD_SECONDS = 2.0


class AirWheelController:
    """Owns the live camera/tracking/steering/controller pipeline and drives
    the MainWindow from it. One instance per running app."""

    def __init__(self, window, settings: AppSettings):
        self.window = window
        self.settings = settings
        self.profile_manager = ProfileManager()

        self.camera: CameraStream | None = None
        self.tracker: HandTracker | None = None
        self.session: SteeringSession | None = None

        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)

        self._calibrating = False
        self._calibration_samples: list[CalibrationSample] = []
        self._calibration_deadline = 0.0
        self._frame_count = 0
        self._last_fps_ts = time.monotonic()
        self._fps = 0.0

        self._populate_profiles()
        self._connect_signals()
        self._connect_shortcuts()

    # -- setup -------------------------------------------------------
    def _populate_profiles(self) -> None:
        names = self.profile_manager.list_names()
        self.window.profile_combo.clear()
        self.window.profile_combo.addItems(names)
        idx = self.window.profile_combo.findText(self.settings.active_profile)
        self.window.profile_combo.setCurrentIndex(max(idx, 0))

    def _connect_signals(self) -> None:
        self.window.start_requested.connect(self.on_start)
        self.window.stop_requested.connect(self.on_stop)
        self.window.calibrate_requested.connect(self.on_calibrate)
        self.window.emergency_requested.connect(self.on_emergency)
        self.window.backend_combo.currentTextChanged.connect(self.on_backend_changed)

    def on_backend_changed(self, text: str) -> None:
        if text == self.settings.output.backend:
            return
        self.settings.output.backend = text
        save_settings(self.settings)
        log.info("Output backend set to %s", text)
        if self.timer.isActive():
            self._show_error(
                f"Output backend set to '{text}'. Click STOP then START again "
                "to reconnect using the new backend."
            )

    def _connect_shortcuts(self) -> None:
        # In-app only - true system-wide hotkeys (so F12 works while a game
        # has focus) need the Windows-only 'keyboard' package + admin, which
        # this module doesn't add on its own. See README "Known limitation".
        hotkey = self.settings.output.emergency_stop_hotkey or "F12"
        QShortcut(QKeySequence(hotkey), self.window, activated=self.on_emergency)

    def _show_error(self, message: str) -> None:
        log.error(message)
        QMessageBox.critical(self.window, "AirWheel", message)

    def _build_controller_backend(self) -> VirtualController:
        if self.settings.output.backend == "keyboard":
            return KeyboardController()
        return XInputGamepadController()

    def _build_session(self) -> SteeringSession | None:
        profile_name = self.window.profile_combo.currentText()
        profile = self.profile_manager.load(profile_name) or GameProfile()

        try:
            backend = self._build_controller_backend()
        except RuntimeError as exc:
            self._show_error(
                f"Controller backend unavailable: {exc}\n\n"
                "Switch Output backend to 'keyboard' in settings, or install "
                "the missing dependency (see docs/DRIVER_SETUP.md)."
            )
            return None

        engine = SteeringEngine(SteeringConfig(
            max_angle_deg=profile.max_angle_deg,
            sensitivity=profile.sensitivity,
            deadzone_pct=profile.deadzone_pct,
            response_curve=profile.response_curve,
            smoothing=profile.smoothing,
            invert=profile.invert_steering,
        ))
        throttle_engine = PedalEngine() if profile.throttle_mode == "virtual_axis" else None
        brake_engine = PedalEngine() if profile.brake_mode == "virtual_axis" else None
        if throttle_engine is not None:
            throttle_engine.calibrate(top_y=0.15, bottom_y=0.85)
        if brake_engine is not None:
            brake_engine.calibrate(top_y=0.15, bottom_y=0.85)

        return SteeringSession(
            engine, backend,
            throttle_engine=throttle_engine, brake_engine=brake_engine,
            gestures_enabled=self.settings.gestures.enabled,
            gesture_hold_seconds=self.settings.gestures.hold_seconds,
        )

    # -- START / STOP ------------------------------------------------
    def on_start(self) -> None:
        if self.timer.isActive():
            return

        if not DEFAULT_MODEL_PATH.exists():
            self._show_error(
                "Hand-tracking model not found.\n\n"
                "Run this in your terminal, then restart AirWheel:\n"
                "    python scripts\\download_model.py"
            )
            return

        session = self._build_session()
        if session is None:
            return
        if not session.start():
            self._show_error(
                f"Could not connect the '{self.settings.output.backend}' controller backend. "
                "Check docs/DRIVER_SETUP.md and the log file."
            )
            self.window.set_state(AppState.CONTROLLER_ERROR)
            return
        self.session = session

        try:
            self.tracker = HandTracker()
        except (RuntimeError, FileNotFoundError) as exc:
            self._show_error(str(exc))
            self.session.stop()
            self.session = None
            return

        self.camera = CameraStream(
            device_index=self.settings.camera.device_index,
            width=self.settings.camera.width,
            height=self.settings.camera.height,
            fps=self.settings.camera.fps,
        )
        if not self.camera.start():
            self._show_error(
                f"Could not open camera #{self.settings.camera.device_index}. "
                "Check it's plugged in, allowed in Windows camera privacy "
                "settings, and not already in use by another app."
            )
            self.tracker.close()
            self.tracker = None
            self.session.stop()
            self.session = None
            self.window.set_state(AppState.CAMERA_ERROR)
            return

        if self.session.engine.center_deg is None:
            # First run this session: default to "straight ahead" so START
            # isn't a dead end, but make it obvious real calibration is
            # still needed for accurate steering.
            self.session.calibrate_center(0.0)

        self._frame_count = 0
        self._last_fps_ts = time.monotonic()
        interval_ms = max(10, int(1000 / max(self.settings.camera.fps, 1)))
        self.timer.start(interval_ms)

        self.window.set_input_active(True)
        self.window.set_state(AppState.ACTIVE)
        log.info("Started: camera=%s tracker=ready backend=%s",
                  self.settings.camera.device_index, self.settings.output.backend)

        if self.settings.output.backend == "keyboard":
            # The single most common "nothing happens" report: simulated key
            # presses go to whichever window has OS focus, not to AirWheel.
            QMessageBox.information(
                self.window, "Keyboard mode",
                "AirWheel will send LEFT/RIGHT key presses to whichever "
                "window currently has focus.\n\n"
                "Click into your game/browser tab now, and don't click back "
                "on the AirWheel window - Windows will route the simulated "
                "keys to AirWheel instead of the game if you do."
            )

    def on_stop(self) -> None:
        self.timer.stop()
        if self.session is not None:
            self.session.stop()
        if self.camera is not None:
            self.camera.stop()
            self.camera = None
        if self.tracker is not None:
            self.tracker.close()
            self.tracker = None
        self.window.set_input_active(False)
        self.window.set_state(AppState.STOPPED)
        self.window.camera_preview.setPixmap(QPixmap())
        self.window.camera_preview.setText("CAMERA PREVIEW\n(not started)")

    def on_emergency(self) -> None:
        if self.session is not None:
            self.session.emergency_stop()
        self.window.set_state(AppState.EMERGENCY_STOP)
        self.window.set_input_active(False)
        log.warning("Emergency stop triggered from UI/hotkey")

    def reset_emergency(self) -> None:
        if self.session is not None:
            self.session.reset_emergency()
        self.window.set_state(AppState.STOPPED)

    # -- CALIBRATE -----------------------------------------------------
    def on_calibrate(self) -> None:
        if self.camera is None or self.tracker is None or self.session is None:
            self._show_error("Press START first so the camera is running, then CALIBRATE.")
            return
        self._calibration_samples = []
        self._calibrating = True
        self._calibration_deadline = time.monotonic() + CALIBRATION_HOLD_SECONDS
        self.window.set_state(AppState.CALIBRATING)

    def _finish_calibration(self) -> None:
        self._calibrating = False
        if len(self._calibration_samples) < MIN_SAMPLES:
            self._show_error(
                "Calibration failed - couldn't see both hands clearly for long "
                "enough. Improve lighting or move closer, then try again."
            )
            self.window.set_state(AppState.ACTIVE)
            return
        result = compute_calibration(self._calibration_samples)
        self.session.calibrate_center(result.center_angle_deg)
        if result.quality_notes:
            self._show_error("Calibrated (quality %d%%), but: %s" % (
                result.quality_score, " ".join(result.quality_notes)))
        self.window.set_state(AppState.ACTIVE)

    # -- per-frame tick --------------------------------------------------
    def _on_tick(self) -> None:
        if self.camera is None or self.tracker is None or self.session is None:
            return

        frame_bgr, ts_ms = self.camera.get_latest_frame()
        if frame_bgr is None:
            if not self.camera.is_connected:
                self._show_error("Camera disconnected.")
                self.on_stop()
            return

        if self.settings.camera.mirror_preview:
            frame_bgr = mirror(frame_bgr)

        pix = bgr_to_pixmap(frame_bgr).scaled(
            self.window.camera_preview.width(),
            self.window.camera_preview.height(),
            Qt.KeepAspectRatio,
        )
        self.window.camera_preview.setPixmap(pix)

        self._frame_count += 1
        now = time.monotonic()
        if now - self._last_fps_ts >= 1.0:
            self._fps = self._frame_count / (now - self._last_fps_ts)
            self._frame_count = 0
            self._last_fps_ts = now

        result = self.tracker.process(to_rgb(frame_bgr), ts_ms)
        left, right = split_left_right(result.hands)
        both_ok = (
            left is not None and right is not None
            and left.confidence >= MIN_HAND_CONFIDENCE
            and right.confidence >= MIN_HAND_CONFIDENCE
        )

        angle = None
        if both_ok:
            lp = Point(*wrist_point(left))
            rp = Point(*wrist_point(right))
            angle = two_hand_angle_deg(lp, rp)

            if self._calibrating:
                sep = hand_separation(lp, rp)
                avg_conf = (left.confidence + right.confidence) / 2
                self._calibration_samples.append(
                    CalibrationSample(angle_deg=angle, separation=sep, confidence=avg_conf)
                )
                if now >= self._calibration_deadline:
                    self._finish_calibration()
            else:
                self.session.update_with_angle(angle, now=now)
                if self.settings.gestures.enabled:
                    self.session.handle_pose_event(classify_hand_pose(left.landmarks), now=now)
        elif not self._calibrating:
            self.session.update_tracking_lost(now=now)

        self._update_telemetry(result_hand_count=len(result.hands), angle=angle, both_ok=both_ok)

    def _update_telemetry(self, result_hand_count: int, angle: float | None, both_ok: bool) -> None:
        steering_val = self.session.engine.last_output
        self.window.set_wheel_angle(steering_val)
        tracking = "GOOD" if both_ok else ("CALIBRATING" if self._calibrating else "LOST")
        self.window.telemetry.update_values(
            fps=f"{self._fps:.0f}",
            hands=str(result_hand_count),
            tracking=tracking,
            steering=f"{steering_val * 100:+.0f}%",
            angle=f"{angle:.1f}°" if angle is not None else "--",
            output=f"{steering_val:+.2f}",
        )
        throttle_val = self.session.throttle_engine.last_output if self.session.throttle_engine else None
        brake_val = self.session.brake_engine.last_output if self.session.brake_engine else None
        self.window.pedal_panel.update_values(steering_val, throttle_val, brake_val)
