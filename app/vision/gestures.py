"""Optional driving gestures (spec sections 12, 20, 29, 73, 92).

Pure landmark math + a debounce/confirmation layer - no camera or MediaPipe
runtime dependency, fully unit-testable with synthetic landmark points.

All gestures are OFF by default (spec sections 20, 29): callers must opt in.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum

# MediaPipe hand landmark indices (0-20).
WRIST = 0
FINGERS = {
    "index": (5, 8),    # (MCP, TIP)
    "middle": (9, 12),
    "ring": (13, 16),
    "pinky": (17, 20),
}


class HandPose(str, Enum):
    OPEN_PALM = "open_palm"
    FIST = "fist"
    OTHER = "other"


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _xy(landmarks: list[tuple[float, float, float]], i: int) -> tuple[float, float]:
    x, y, _z = landmarks[i]
    return (x, y)


def count_extended_fingers(landmarks: list[tuple[float, float, float]], extend_ratio: float = 1.15) -> int:
    """A finger counts as extended if its tip is meaningfully farther from
    the wrist than its MCP knuckle is. Thumb is excluded (its geometry
    differs too much for this simple heuristic to be reliable)."""
    wrist = _xy(landmarks, WRIST)
    count = 0
    for mcp_idx, tip_idx in FINGERS.values():
        mcp = _xy(landmarks, mcp_idx)
        tip = _xy(landmarks, tip_idx)
        if _dist(wrist, tip) > _dist(wrist, mcp) * extend_ratio:
            count += 1
    return count


def classify_hand_pose(landmarks: list[tuple[float, float, float]]) -> HandPose:
    extended = count_extended_fingers(landmarks)
    if extended >= 3:
        return HandPose.OPEN_PALM
    if extended <= 1:
        return HandPose.FIST
    return HandPose.OTHER


def hands_close_together(
    left_wrist: tuple[float, float], right_wrist: tuple[float, float],
    reference_separation: float, ratio_threshold: float = 0.4,
) -> bool:
    """True if the wrists have been brought in to less than ratio_threshold
    of the calibrated reference separation (spec section 29, recentering)."""
    if reference_separation <= 1e-6:
        return False
    return _dist(left_wrist, right_wrist) < reference_separation * ratio_threshold


@dataclass
class DebouncedEvent:
    """Fires a value only once it has been continuously reported for at
    least `hold_seconds` (spec section 92 - prevents one noisy frame from
    triggering a disruptive gesture)."""
    hold_seconds: float = 0.4
    _current: object = None
    _since: float | None = None
    _confirmed: object = None

    def update(self, value: object, now: float | None = None) -> object | None:
        """Feed the latest raw reading. Returns the confirmed value the
        instant it crosses the hold threshold, then None on subsequent
        frames until `value` changes again (edge-triggered, not level)."""
        now = now if now is not None else time.monotonic()
        if value != self._current:
            self._current = value
            self._since = now
            self._confirmed = None
            return None
        if self._confirmed == value:
            return None  # already fired for this held value
        if self._since is not None and (now - self._since) >= self.hold_seconds:
            self._confirmed = value
            return value
        return None

    def reset(self) -> None:
        self._current = None
        self._since = None
        self._confirmed = None
