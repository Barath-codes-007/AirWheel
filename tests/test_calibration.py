import pytest

from app.steering.calibration import CalibrationSample, compute_calibration


def steady_samples(n=15, angle=0.0, sep=0.3, conf=0.95):
    return [CalibrationSample(angle_deg=angle, separation=sep, confidence=conf) for _ in range(n)]


def test_too_few_samples_raises():
    with pytest.raises(ValueError):
        compute_calibration(steady_samples(n=3))


def test_steady_high_confidence_scores_high():
    result = compute_calibration(steady_samples())
    assert result.quality_score >= 90
    assert result.center_angle_deg == pytest.approx(0.0)


def test_jittery_hands_lower_score_and_add_note():
    samples = [
        CalibrationSample(angle_deg=a, separation=0.3, confidence=0.95)
        for a in [0, 10, -8, 12, -15, 6, -9, 11, -7, 13, 0, 5, -5, 8, -8]
    ]
    result = compute_calibration(samples)
    assert result.quality_score < 90
    assert any("still" in n for n in result.quality_notes)


def test_low_confidence_lowers_score():
    result = compute_calibration(steady_samples(conf=0.4))
    assert result.quality_score < 70
    assert any("confidence" in n for n in result.quality_notes)


def test_hands_too_close_together_flagged():
    result = compute_calibration(steady_samples(sep=0.05))
    assert any("apart" in n for n in result.quality_notes)


def test_reference_separation_is_mean():
    result = compute_calibration(steady_samples(sep=0.4))
    assert result.reference_separation == pytest.approx(0.4)
