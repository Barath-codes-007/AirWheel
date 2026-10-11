import math

import pytest

from app.steering.engine import (
    EmaSmoother, SteeringConfig, SteeringEngine, angle_diff, apply_deadzone,
    apply_response_curve, clamp,
)


def test_angle_diff_basic():
    assert angle_diff(10, 0) == 10
    assert angle_diff(0, 10) == -10
    assert angle_diff(350, 10) == -20  # wraps the short way


def test_angle_diff_wrap_no_jump():
    # crossing +180/-180 must not produce a huge jump
    assert abs(angle_diff(179, -179)) <= 2
    assert abs(angle_diff(-179, 179)) <= 2


def test_normalize_angle_via_engine():
    # "low" smoothing still eases in from the post-calibration center, so
    # feed a few identical frames (as a real camera loop would) and check
    # the settled value rather than the very first frame.
    e = SteeringEngine(SteeringConfig(max_angle_deg=60, deadzone_pct=0, smoothing="low"))
    e.calibrate_center(0)
    for _ in range(10):
        v = e.update(60)
    assert v == pytest.approx(1.0, abs=0.05)

    e2 = SteeringEngine(SteeringConfig(max_angle_deg=60, deadzone_pct=0, smoothing="low"))
    e2.calibrate_center(0)
    for _ in range(10):
        v2 = e2.update(-60)
    assert v2 == pytest.approx(-1.0, abs=0.05)


def test_deadzone_zeroes_small_input_and_rescales_edge():
    assert apply_deadzone(0.01, 5) == 0.0
    assert apply_deadzone(0.0, 5) == 0.0
    assert apply_deadzone(1.0, 5) == pytest.approx(1.0)
    assert apply_deadzone(-1.0, 10) == pytest.approx(-1.0)


def test_response_curve_progressive_softens_small_inputs():
    assert apply_response_curve(0.5, "progressive") < 0.5
    assert apply_response_curve(0.5, "aggressive") > 0.5
    assert apply_response_curve(1.0, "aggressive") == 1.0
    assert apply_response_curve(-0.5, "progressive") < 0  # sign preserved


def test_sensitivity_scales_output():
    lo = SteeringEngine(SteeringConfig(max_angle_deg=60, deadzone_pct=0, sensitivity=0.5, smoothing="low"))
    hi = SteeringEngine(SteeringConfig(max_angle_deg=60, deadzone_pct=0, sensitivity=2.0, smoothing="low"))
    lo.calibrate_center(0); hi.calibrate_center(0)
    assert abs(lo.update(20)) < abs(hi.update(20))


def test_clamp():
    assert clamp(5) == 1.0
    assert clamp(-5) == -1.0
    assert clamp(0.3) == 0.3


def test_smoothing_reduces_single_frame_jump():
    s = EmaSmoother("high")
    s.reset(0.0)
    first = s.update(1.0)
    assert 0 < first < 1.0  # heavy smoothing: doesn't jump straight to 1


def test_tracking_loss_returns_toward_center():
    e = SteeringEngine(SteeringConfig(center_return_rate=0.5, deadzone_pct=0, smoothing="low"))
    e.calibrate_center(0)
    e.update(60)
    v1 = e.on_tracking_lost_tick()
    v2 = e.on_tracking_lost_tick()
    assert abs(v1) > abs(v2) >= 0
    for _ in range(30):
        v2 = e.on_tracking_lost_tick()
    assert v2 == 0.0  # settles exactly at center, never stuck off-center


def test_centering_calibration_resets_output():
    e = SteeringEngine()
    e.calibrate_center(45)
    assert e.update(45) == pytest.approx(0.0, abs=0.05)


def test_emergency_stop_forces_zero_immediately():
    e = SteeringEngine(SteeringConfig(deadzone_pct=0, smoothing="low"))
    e.calibrate_center(0)
    e.update(60)
    assert e.emergency_stop() == 0.0
    assert e.last_output == 0.0


def test_invert_flips_sign():
    normal = SteeringEngine(SteeringConfig(deadzone_pct=0, smoothing="low"))
    inverted = SteeringEngine(SteeringConfig(deadzone_pct=0, smoothing="low", invert=True))
    normal.calibrate_center(0); inverted.calibrate_center(0)
    assert normal.update(30) > 0
    assert inverted.update(30) < 0


def test_update_before_calibration_raises():
    e = SteeringEngine()
    with pytest.raises(RuntimeError):
        e.update(10)


def test_profile_serialization_roundtrip():
    from dataclasses import asdict
    c = SteeringConfig(max_angle_deg=90, sensitivity=1.5, response_curve="soft")
    d = asdict(c)
    c2 = SteeringConfig(**d)
    assert c2 == c
