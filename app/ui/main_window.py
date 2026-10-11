"""Main dashboard window (spec sections 22, 30, 38, 39, 43, 114, 115).

IMPORTANT - not runnable/tested in this environment: PySide6 is not
installed in this dev sandbox (no network to install it here), and there is
no display to render against. This module is written against the
documented PySide6/Qt Widgets API but has NOT been executed. Run it on your
Windows machine (`pip install PySide6`, then `python -m app.main`) and treat
it as EXPERIMENTAL until you've actually seen it render.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)

from app.config import AppSettings
from app.state import AppState
from app.ui.pedal_widget import PedalPanel

log = logging.getLogger("airwheel.ui")

DARK_QSS = """
QMainWindow, QWidget { background-color: #14161c; color: #e6e8ec; font-family: 'Segoe UI'; }
QPushButton { background-color: #1f2430; border: 1px solid #33394a; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background-color: #2a2f3d; }
QPushButton:disabled { color: #666a75; }
QPushButton#primary { background-color: #3d6bff; border: none; font-weight: 600; }
QPushButton#danger { background-color: #b3261e; border: none; font-weight: 600; }
QLabel#statusGood { color: #3ddc84; font-weight: 600; }
QLabel#statusWarn { color: #ffb020; font-weight: 600; }
QLabel#statusBad { color: #ff5c5c; font-weight: 600; }
QLabel#heading { font-size: 18px; font-weight: 700; }
QFrame#panel { background-color: #1a1d26; border: 1px solid #262b38; border-radius: 10px; }
"""

_STATE_LABELS: dict[AppState, tuple[str, str]] = {    AppState.IDLE: ("IDLE", "statusWarn"),
    AppState.INITIALIZING: ("INITIALIZING", "statusWarn"),
    AppState.CALIBRATING: ("CALIBRATING", "statusWarn"),
    AppState.READY: ("READY", "statusGood"),
    AppState.ACTIVE: ("ACTIVE", "statusGood"),
    AppState.TRACKING_LOST: ("TRACKING LOST", "statusBad"),
    AppState.CAMERA_ERROR: ("CAMERA ERROR", "statusBad"),
    AppState.CONTROLLER_ERROR: ("CONTROLLER ERROR", "statusBad"),
    AppState.EMERGENCY_STOP: ("EMERGENCY STOP", "statusBad"),
    AppState.STOPPED: ("STOPPED", "statusWarn"),
}


def _draw_wheel_pixmap(diameter: int = 180) -> QPixmap:
    """Procedurally draws a simple steering-wheel glyph (rim + 3 spokes +
    hub) - spec section 13's virtual wheel overlay, done directly in Qt
    rather than as a bundled image asset."""
    pm = QPixmap(diameter, diameter)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#3d6bff"))
    pen.setWidth(max(4, diameter // 22))
    painter.setPen(pen)
    margin = diameter // 8
    painter.drawEllipse(margin, margin, diameter - 2 * margin, diameter - 2 * margin)
    cx = cy = diameter // 2
    for angle_deg in (90, 210, 330):  # three spokes, 120 degrees apart
        import math
        rad = math.radians(angle_deg)
        x = cx + (diameter // 2 - margin) * math.cos(rad)
        y = cy - (diameter // 2 - margin) * math.sin(rad)
        painter.drawLine(cx, cy, int(x), int(y))
    hub_r = diameter // 10
    painter.setBrush(QColor("#3d6bff"))
    painter.drawEllipse(cx - hub_r, cy - hub_r, hub_r * 2, hub_r * 2)
    painter.end()
    return pm


class TelemetryPanel(QFrame):
    """Live numbers (spec section 23): FPS, latency, hands, steering, angle."""

    def __init__(self):
        super().__init__()
        self.setObjectName("panel")
        layout = QGridLayout(self)
        self._value_labels: dict[str, QLabel] = {}
        rows = [
            ("fps", "FPS"), ("latency", "Latency"), ("hands", "Hands"),
            ("tracking", "Tracking"), ("steering", "Steering"), ("angle", "Angle"),
            ("output", "Output"),
        ]
        for i, (key, label) in enumerate(rows):
            layout.addWidget(QLabel(label), i, 0)
            value = QLabel("--")
            value.setAlignment(Qt.AlignRight)
            layout.addWidget(value, i, 1)
            self._value_labels[key] = value

    def update_values(self, **kwargs: str) -> None:
        for key, text in kwargs.items():
            if key in self._value_labels:
                self._value_labels[key].setText(text)


class MainWindow(QMainWindow):
    calibrate_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    emergency_requested = Signal()

    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("AirWheel — Virtual Steering Controller")
        self.resize(980, 620)
        self.setStyleSheet(DARK_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        header = QHBoxLayout()
        title = QLabel("AIRWHEEL")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch(1)
        self.state_label = QLabel("IDLE")
        self.state_label.setObjectName("statusWarn")
        header.addWidget(self.state_label)
        root.addLayout(header)

        body = QHBoxLayout()
        self.camera_preview = QLabel("CAMERA PREVIEW\n(not started)")
        self.camera_preview.setObjectName("panel")
        self.camera_preview.setAlignment(Qt.AlignCenter)
        self.camera_preview.setMinimumSize(420, 320)
        body.addWidget(self.camera_preview, 2)

        wheel_container = QWidget()
        wheel_layout = QVBoxLayout(wheel_container)
        self.wheel_preview = QLabel()
        self.wheel_preview.setObjectName("panel")
        self.wheel_preview.setAlignment(Qt.AlignCenter)
        self.wheel_preview.setMinimumSize(220, 260)
        self._wheel_base_pixmap = _draw_wheel_pixmap(180)
        self.wheel_preview.setPixmap(self._wheel_base_pixmap)
        self.wheel_angle_label = QLabel("0%")
        self.wheel_angle_label.setAlignment(Qt.AlignCenter)
        wheel_layout.addWidget(self.wheel_preview)
        wheel_layout.addWidget(self.wheel_angle_label)
        body.addWidget(wheel_container, 1)

        self.telemetry = TelemetryPanel()
        body.addWidget(self.telemetry, 1)
        root.addLayout(body, 1)

        # Phase 9: pedal bars only shown once a profile actually enables a
        # pedal (spec section 89) - hidden by default, matching PedalSettings.
        self.pedal_panel = PedalPanel(
            show_throttle=settings.pedals.throttle_mode != "off",
            show_brake=settings.pedals.brake_mode != "off",
        )
        self.pedal_panel.setVisible(
            settings.pedals.throttle_mode != "off" or settings.pedals.brake_mode != "off"
        )
        root.addWidget(self.pedal_panel)

        controls = QHBoxLayout()
        self.calibrate_btn = QPushButton("CALIBRATE")
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("primary")
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setEnabled(False)
        self.emergency_btn = QPushButton("EMERGENCY STOP (F12)")
        self.emergency_btn.setObjectName("danger")

        for btn, signal in (
            (self.calibrate_btn, self.calibrate_requested),
            (self.start_btn, self.start_requested),
            (self.stop_btn, self.stop_requested),
            (self.emergency_btn, self.emergency_requested),
        ):
            btn.clicked.connect(signal.emit)
            controls.addWidget(btn)
        root.addLayout(controls)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        input_row.addWidget(self.profile_combo)

        input_row.addWidget(QLabel("Output:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["virtual_gamepad", "keyboard"])
        idx = self.backend_combo.findText(settings.output.backend)
        self.backend_combo.setCurrentIndex(max(idx, 0))
        self.backend_combo.setToolTip(
            "virtual_gamepad: analog, needs a game that reads a gamepad axis.\n"
            "keyboard: digital LEFT/RIGHT, for games/websites that only read arrow keys.\n"
            "Change takes effect on the next START."
        )
        input_row.addWidget(self.backend_combo)

        input_row.addStretch(1)
        self.input_status_label = QLabel("INPUT: OFF")
        self.input_status_label.setObjectName("statusWarn")
        input_row.addWidget(self.input_status_label)
        root.addLayout(input_row)

    # -- called by the controller/orchestrator, not internally ----------
    def set_wheel_angle(self, steering_value: float, display_max_deg: float = 90.0) -> None:
        """steering_value in [-1, 1]. Purely a display convenience - always
        shows +-90 degrees of rotation at full lock regardless of the
        profile's actual calibrated max_angle_deg, so it stays readable."""
        degrees = max(-1.0, min(1.0, steering_value)) * display_max_deg
        rotated = self._wheel_base_pixmap.transformed(QTransform().rotate(degrees), Qt.SmoothTransformation)
        self.wheel_preview.setPixmap(rotated)
        self.wheel_angle_label.setText(f"{steering_value * 100:+.0f}%")

    def set_state(self, state: AppState) -> None:
        text, style = _STATE_LABELS.get(state, (state.value, "statusWarn"))
        self.state_label.setText(text)
        self.state_label.setObjectName(style)
        self.state_label.setStyleSheet(self.state_label.styleSheet())  # re-apply QSS by object name

    def set_input_active(self, active: bool) -> None:
        self.input_status_label.setText("INPUT: ACTIVE" if active else "INPUT: OFF")
        self.input_status_label.setObjectName("statusGood" if active else "statusWarn")
        self.start_btn.setEnabled(not active)
        self.stop_btn.setEnabled(active)

    def confirm_exit_or_tray(self) -> str:
        """Returns 'exit', 'tray', or 'cancel' (spec section 96)."""
        box = QMessageBox(self)
        box.setWindowTitle("Close AirWheel")
        box.setText("Exit AirWheel, or minimize to the system tray and keep it running?")
        exit_btn = box.addButton("Exit AirWheel", QMessageBox.DestructiveRole)
        tray_btn = box.addButton("Minimize to Tray", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is exit_btn:
            return "exit"
        if clicked is tray_btn:
            return "tray"
        return "cancel"

    def closeEvent(self, event) -> None:
        # Only prompt if AirWheel is actually sending input right now -
        # closing an idle window shouldn't require a decision.
        controller = getattr(self, "_controller", None)
        is_active = self.stop_btn.isEnabled()  # STOP is only enabled while ACTIVE
        if not is_active:
            if controller is not None:
                controller.on_stop()
            event.accept()
            return

        choice = self.confirm_exit_or_tray()
        if choice == "exit":
            if controller is not None:
                controller.on_stop()
            event.accept()
        elif choice == "tray":
            event.ignore()
            self.hide()
        else:
            event.ignore()
