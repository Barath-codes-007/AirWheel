"""Steering math engine (spec sections 5, 62-70).

Pure math, no I/O — fully unit-testable without a camera.

Pipeline: raw angle -> center offset -> angle normalization -> deadzone ->
sensitivity -> response curve -> smoothing -> clamp -> final steering.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def angle_diff(a: float, b: float) -> float:
    """Shortest signed difference a - b in degrees, wrapped to (-180, 180]."""
    d = (a - b + 180.0) % 360.0 - 180.0
    return 180.0 if d == -180.0 else d


def clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def apply_deadzone(normalized: float, deadzone_pct: float) -> float:
    """normalized in [-1, 1]; deadzone_pct in [0, 100]. Rescales so output
    still reaches +-1 at the edges instead of leaving a dead band at the top."""
    dz = clamp(deadzone_pct, 0.0, 100.0) / 100.0
    mag = abs(normalized)
    if mag <= dz:
        return 0.0
    sign = 1.0 if normalized > 0 else -1.0
    return sign * (mag - dz) / (1.0 - dz) if dz < 1.0 else 0.0


def apply_response_curve(value: float, curve: str) -> float:
    """value in [-1, 1]. Curve reshapes the magnitude; sign is preserved."""
    sign = 1.0 if value >= 0 else -1.0
    mag = min(abs(value), 1.0)
    if curve == "linear":
        out = mag
    elif curve == "progressive":
        out = mag ** 2
    elif curve == "soft":
        out = mag ** 0.5
    elif curve == "aggressive":
        out = min(mag * 1.6, 1.0)
    else:
        out = mag
    return sign * out


class EmaSmoother:
    """Exponential moving average smoother."""

    _ALPHA_BY_LEVEL = {"low": 0.8, "medium": 0.5, "high": 0.25}

    def __init__(self, level: str = "medium"):
        self.alpha = self._ALPHA_BY_LEVEL.get(level, 0.5)
        self._value: float | None = None

    def reset(self, value: float = 0.0) -> None:
        self._value = value

    def update(self, raw: float) -> float:
        if self._value is None:
            self._value = raw
        else:
            self._value = self.alpha * raw + (1 - self.alpha) * self._value
        return self._value


@dataclass
class SteeringConfig:
    max_angle_deg: float = 60.0
    sensitivity: float = 1.0
    deadzone_pct: float = 2.0
    response_curve: str = "linear"
    smoothing: str = "medium"
    invert: bool = False
    center_return_rate: float = 0.15  # fraction moved toward 0 per tick while tracking is lost


class SteeringEngine:
    """Stateful engine: feed it a hand angle or a tracking-loss tick, get steering out."""

    def __init__(self, config: SteeringConfig | None = None):
        self.config = config or SteeringConfig()
        self._smoother = EmaSmoother(self.config.smoothing)
        self.center_deg: float | None = None
        self.last_output: float = 0.0

    def calibrate_center(self, angle_deg: float) -> None:
        self.center_deg = angle_deg
        self._smoother.reset(0.0)
        self.last_output = 0.0

    def set_smoothing(self, level: str) -> None:
        self.config.smoothing = level
        self._smoother = EmaSmoother(level)

    def update(self, angle_deg: float) -> float:
        """Feed a fresh hand-vector angle in degrees; returns final steering in [-1, 1]."""
        if self.center_deg is None:
            raise RuntimeError("SteeringEngine.calibrate_center() must be called before update()")

        offset = angle_diff(angle_deg, self.center_deg)
        max_angle = max(self.config.max_angle_deg, 1e-6)
        normalized = clamp(offset / max_angle)
        after_deadzone = apply_deadzone(normalized, self.config.deadzone_pct)
        sensed = clamp(after_deadzone * clamp(self.config.sensitivity, 0.5, 2.0))
        curved = apply_response_curve(sensed, self.config.response_curve)
        if self.config.invert:
            curved = -curved
        smoothed = self._smoother.update(curved)
        self.last_output = clamp(smoothed)
        return self.last_output

    def on_tracking_lost_tick(self) -> float:
        """Call once per frame while tracking is lost; moves output toward 0."""
        rate = clamp(self.config.center_return_rate, 0.01, 1.0)
        self.last_output = self.last_output * (1.0 - rate)
        if abs(self.last_output) < 1e-3:
            self.last_output = 0.0
        self._smoother.reset(self.last_output)
        return self.last_output

    def emergency_stop(self) -> float:
        self.last_output = 0.0
        self._smoother.reset(0.0)
        return 0.0
