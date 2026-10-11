"""Calibration wizard logic and quality scoring (spec sections 6, 37, 78).

Pure logic: given a short buffer of angle samples taken while the user
holds the "centered" pose still, compute the center angle, hand-separation
reference, and a 0-100 calibration quality score. No camera/UI dependency.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationSample:
    angle_deg: float
    separation: float
    confidence: float  # 0-1, average of both hands' tracking confidence


@dataclass(frozen=True)
class CalibrationResult:
    center_angle_deg: float
    reference_separation: float
    quality_score: int  # 0-100
    quality_notes: list[str]


MIN_SAMPLES = 10


def compute_calibration(samples: list[CalibrationSample]) -> CalibrationResult:
    if len(samples) < MIN_SAMPLES:
        raise ValueError(f"need at least {MIN_SAMPLES} samples, got {len(samples)}")

    angles = [s.angle_deg for s in samples]
    seps = [s.separation for s in samples]
    confidences = [s.confidence for s in samples]

    center_angle = statistics.mean(angles)
    reference_sep = statistics.mean(seps)

    angle_jitter = statistics.pstdev(angles)       # degrees; lower = steadier hold
    sep_jitter = statistics.pstdev(seps) / max(reference_sep, 1e-6)
    avg_confidence = statistics.mean(confidences)

    notes: list[str] = []
    score = 100.0

    # Confidence: below 0.8 starts costing points.
    if avg_confidence < 0.8:
        penalty = (0.8 - avg_confidence) * 150
        score -= penalty
        notes.append("Tracking confidence was low during calibration.")

    # Stability: penalize hand wobble while "holding still".
    if angle_jitter > 2.0:
        score -= min((angle_jitter - 2.0) * 5, 40)
        notes.append("Hands weren't fully still - try to hold the pose steady.")
    if sep_jitter > 0.05:
        score -= min((sep_jitter - 0.05) * 200, 30)
        notes.append("Hand distance from camera varied - try to stay still.")

    # Separation: too close together makes the angle noisy/ambiguous.
    if reference_sep < 0.15:
        score -= 20
        notes.append("Hands were close together - move them farther apart.")

    score = max(0, min(100, round(score)))
    if score < 60 and not notes:
        notes.append("Calibration quality is low - consider recalibrating.")
    return CalibrationResult(
        center_angle_deg=center_angle,
        reference_separation=reference_sep,
        quality_score=score,
        quality_notes=notes,
    )
