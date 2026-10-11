"""Two-hand steering-wheel geometry (spec sections 5, 70, 71, 74).

Pure math over landmark coordinates — no camera or MediaPipe dependency,
so it is fully unit-testable with synthetic points.

Landmarks are (x, y) in normalized image coordinates (0-1), MediaPipe's
convention where +x is right and +y is DOWN. Angle is measured with
atan2(-dy, dx) so that a visually clockwise rotation (right hand higher,
left hand lower -> turning right) yields a decreasing angle, matching
steering "turn right = positive" once combined with the engine's sign
convention. invert_steering in config can flip this if a user's camera
setup disagrees.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float


def two_hand_angle_deg(left: Point, right: Point) -> float:
    """Angle in degrees of the vector from left hand to right hand.
    0 deg = hands level (wheel centered), positive = right hand raised
    (wheel turned counter-clockwise as drawn / left in wheel terms)."""
    dx = right.x - left.x
    dy = right.y - left.y
    return math.degrees(math.atan2(-dy, dx))


def hand_separation(left: Point, right: Point) -> float:
    return math.hypot(right.x - left.x, right.y - left.y)


def normalize_separation(current: float, reference: float) -> float:
    """Ratio of current hand separation to the calibrated reference (1.0 = same
    distance from camera as during calibration). Guards against divide-by-zero."""
    if reference <= 1e-6:
        return 1.0
    return current / reference


def one_hand_angle_deg(hand: Point, virtual_center: Point) -> float:
    """EXPERIMENTAL one-hand mode: angle of the hand around a fixed virtual
    center point established at calibration (spec section 73)."""
    dx = hand.x - virtual_center.x
    dy = hand.y - virtual_center.y
    return math.degrees(math.atan2(-dy, dx))
