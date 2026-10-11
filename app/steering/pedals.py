"""EXPERIMENTAL throttle/brake from hand vertical position (spec sections
18, 19, 87, 88). OFF by default; never allowed to interfere with steering -
this module has no knowledge of the steering engine at all.

"Hand lower: less throttle. Hand higher: more throttle" (spec section 18).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.steering.engine import EmaSmoother, clamp


@dataclass
class PedalConfig:
    smoothing: str = "medium"
    deadzone_pct: float = 2.0  # ignore tiny movement near the calibrated low point


class PedalEngine:
    """One instance per pedal (throttle or brake). Output is 0.0-1.0."""

    def __init__(self, config: PedalConfig | None = None):
        self.config = config or PedalConfig()
        self._smoother = EmaSmoother(self.config.smoothing)
        self.top_y: float | None = None     # calibrated "hand high" (max value)
        self.bottom_y: float | None = None  # calibrated "hand low" (zero value)
        self.last_output: float = 0.0

    def calibrate(self, top_y: float, bottom_y: float) -> None:
        """top_y/bottom_y are normalized image y-coordinates (0=image top,
        1=image bottom, MediaPipe convention) for the hand's highest and
        lowest comfortable positions."""
        if bottom_y <= top_y:
            raise ValueError("bottom_y must be greater than top_y (lower on screen = larger y)")
        self.top_y = top_y
        self.bottom_y = bottom_y
        self._smoother.reset(0.0)
        self.last_output = 0.0

    def update(self, hand_y: float) -> float:
        if self.top_y is None or self.bottom_y is None:
            raise RuntimeError("PedalEngine.calibrate() must be called before update()")
        span = self.bottom_y - self.top_y
        raw = clamp((self.bottom_y - hand_y) / span, 0.0, 1.0)
        dz = clamp(self.config.deadzone_pct, 0.0, 100.0) / 100.0
        after_deadzone = 0.0 if raw <= dz else (raw - dz) / (1.0 - dz)
        smoothed = clamp(self._smoother.update(after_deadzone), 0.0, 1.0)
        self.last_output = smoothed
        return smoothed

    def on_tracking_lost_tick(self, release_rate: float = 0.3) -> float:
        """Pedals release toward 0 on tracking loss, same safety principle
        as steering returning to center."""
        self.last_output = self.last_output * (1.0 - clamp(release_rate, 0.01, 1.0))
        if self.last_output < 1e-3:
            self.last_output = 0.0
        self._smoother.reset(self.last_output)
        return self.last_output

    def release(self) -> float:
        self.last_output = 0.0
        self._smoother.reset(0.0)
        return 0.0
