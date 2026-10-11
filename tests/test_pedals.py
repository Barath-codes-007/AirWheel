import pytest

from app.steering.pedals import PedalConfig, PedalEngine


def test_calibrate_rejects_inverted_range():
    p = PedalEngine()
    with pytest.raises(ValueError):
        p.calibrate(top_y=0.8, bottom_y=0.2)  # bottom must be numerically larger (lower on screen)


def test_hand_high_gives_high_output():
    p = PedalEngine(PedalConfig(smoothing="low", deadzone_pct=0))
    p.calibrate(top_y=0.2, bottom_y=0.8)
    for _ in range(10):
        v = p.update(0.2)
    assert v == pytest.approx(1.0, abs=0.05)


def test_hand_low_gives_low_output():
    p = PedalEngine(PedalConfig(smoothing="low", deadzone_pct=0))
    p.calibrate(top_y=0.2, bottom_y=0.8)
    for _ in range(10):
        v = p.update(0.8)
    assert v == pytest.approx(0.0, abs=0.05)


def test_output_is_clamped_to_unit_range():
    p = PedalEngine(PedalConfig(smoothing="low", deadzone_pct=0))
    p.calibrate(top_y=0.2, bottom_y=0.8)
    for _ in range(10):
        v_over = p.update(0.0)   # above calibrated top
        v_under = p.update(1.0)  # below calibrated bottom
    assert 0.0 <= v_over <= 1.0
    assert 0.0 <= v_under <= 1.0


def test_deadzone_near_bottom_gives_zero():
    p = PedalEngine(PedalConfig(smoothing="low", deadzone_pct=10))
    p.calibrate(top_y=0.0, bottom_y=1.0)
    for _ in range(10):
        v = p.update(0.95)  # only 5% up from bottom, within 10% deadzone
    assert v == 0.0


def test_tracking_loss_releases_toward_zero_and_settles():
    p = PedalEngine(PedalConfig(smoothing="low", deadzone_pct=0))
    p.calibrate(top_y=0.0, bottom_y=1.0)
    for _ in range(10):
        p.update(0.0)  # full throttle
    v1 = p.on_tracking_lost_tick(release_rate=0.5)
    v2 = p.on_tracking_lost_tick(release_rate=0.5)
    assert v1 > v2
    for _ in range(30):
        v_final = p.on_tracking_lost_tick(release_rate=0.5)
    assert v_final == 0.0


def test_release_forces_zero_immediately():
    p = PedalEngine(PedalConfig(smoothing="low", deadzone_pct=0))
    p.calibrate(top_y=0.0, bottom_y=1.0)
    p.update(0.0)
    assert p.release() == 0.0
    assert p.last_output == 0.0


def test_update_before_calibration_raises():
    p = PedalEngine()
    with pytest.raises(RuntimeError):
        p.update(0.5)
