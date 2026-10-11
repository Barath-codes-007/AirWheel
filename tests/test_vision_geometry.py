import math

import pytest

from app.vision.geometry import (
    Point, hand_separation, normalize_separation, one_hand_angle_deg,
    two_hand_angle_deg,
)


def test_level_hands_is_zero_degrees():
    left = Point(0.3, 0.5)
    right = Point(0.7, 0.5)
    assert two_hand_angle_deg(left, right) == pytest.approx(0.0)


def test_right_hand_raised_is_positive():
    left = Point(0.3, 0.5)
    right = Point(0.7, 0.3)  # smaller y = higher on screen
    assert two_hand_angle_deg(left, right) > 0


def test_right_hand_lowered_is_negative():
    left = Point(0.3, 0.5)
    right = Point(0.7, 0.7)
    assert two_hand_angle_deg(left, right) < 0


def test_hand_separation_and_normalization():
    left = Point(0.0, 0.0)
    right = Point(0.3, 0.4)
    sep = hand_separation(left, right)
    assert sep == pytest.approx(0.5)
    assert normalize_separation(sep, sep) == pytest.approx(1.0)
    assert normalize_separation(sep, 0.0) == 1.0  # guarded, no crash


def test_one_hand_angle_around_virtual_center():
    center = Point(0.5, 0.5)
    hand = Point(0.5, 0.3)  # directly above center
    assert one_hand_angle_deg(hand, center) == pytest.approx(90.0)
