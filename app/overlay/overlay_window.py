"""Small always-on-top overlay for Game Mode (spec sections 27, 93, 94).

Polished for Phase 9: configurable opacity/position/size and per-row
show/hide, all driven by OverlaySettings (app/config/settings.py) rather
than hardcoded. Same caveat as the other ui/ modules: PySide6 isn't
installed and there's no display in this dev sandbox, so this has NOT been
run - written against the documented Qt Widgets API only.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.config.settings import OverlaySettings

_ROW_STYLE = "color: white; background: rgba(20,22,28,{alpha}); padding: 2px 6px;"


class OverlayWindow(QWidget):
    def __init__(self, settings: OverlaySettings | None = None):
        super().__init__()
        self.settings = settings or OverlaySettings()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self.status_label = QLabel("AIRWHEEL ● ACTIVE")
        self.steering_label = QLabel("Steering: 0%")
        self.tracking_label = QLabel("Tracking: --")
        self.controller_label = QLabel("Controller: --")
        self._rows = {
            "status": self.status_label,
            "steering": self.steering_label,
            "tracking": self.tracking_label,
            "controller": self.controller_label,
        }
        for w in self._rows.values():
            self._layout.addWidget(w)

        self.apply_settings(self.settings)

    def apply_settings(self, settings: OverlaySettings) -> None:
        """Re-applies opacity/position/size/visible-rows without recreating
        the window - call after the user changes overlay settings."""
        self.settings = settings
        self.setWindowOpacity(max(0.1, min(1.0, settings.opacity)))
        self.resize(settings.width, settings.height)
        self.move(settings.pos_x, settings.pos_y)
        alpha = int(max(0.0, min(1.0, settings.opacity)) * 255)
        style = _ROW_STYLE.format(alpha=alpha)
        for key, label in self._rows.items():
            label.setStyleSheet(style)
            label.setVisible(getattr(settings, f"show_{key}", True))

    def update_values(self, steering_pct: float, tracking: str, controller: str = "") -> None:
        self.steering_label.setText(f"Steering: {steering_pct:+.0f}%")
        self.tracking_label.setText(f"Tracking: {tracking}")
        if controller:
            self.controller_label.setText(f"Controller: {controller}")
