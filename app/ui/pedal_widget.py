"""Steering/throttle/brake bar widget (spec section 89). Same caveat as the
rest of app/ui: written against the documented PySide6 API, not run here
(no PySide6/display in this dev sandbox).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout


class _Bar(QFrame):
    def __init__(self, label: str, bipolar: bool = False):
        super().__init__()
        self.bipolar = bipolar
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.title = QLabel(label)
        self.bar = QProgressBar()
        if bipolar:
            self.bar.setRange(-100, 100)
        else:
            self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        layout.addWidget(self.title)
        layout.addWidget(self.bar)

    def set_value(self, value: float) -> None:
        """value in [-1,1] for bipolar (steering), [0,1] otherwise."""
        pct = value * 100
        self.bar.setValue(int(round(pct)))
        self.bar.setFormat(f"{pct:+.0f}%" if self.bipolar else f"{pct:.0f}%")


class PedalPanel(QFrame):
    """Live steering/throttle/brake feedback shown when pedals are enabled."""

    def __init__(self, show_throttle: bool = True, show_brake: bool = True):
        super().__init__()
        self.setObjectName("panel")
        layout = QHBoxLayout(self)
        self.steering_bar = _Bar("STEERING", bipolar=True)
        layout.addWidget(self.steering_bar)
        self.throttle_bar = _Bar("THROTTLE") if show_throttle else None
        self.brake_bar = _Bar("BRAKE") if show_brake else None
        if self.throttle_bar:
            layout.addWidget(self.throttle_bar)
        if self.brake_bar:
            layout.addWidget(self.brake_bar)

    def update_values(self, steering: float, throttle: float | None = None, brake: float | None = None) -> None:
        self.steering_bar.set_value(steering)
        if self.throttle_bar is not None and throttle is not None:
            self.throttle_bar.set_value(throttle)
        if self.brake_bar is not None and brake is not None:
            self.brake_bar.set_value(brake)
