"""MediaPipe Hand Landmarker wrapper (spec sections 3, 4).

Uses the current MediaPipe Tasks API (mediapipe.tasks.python.vision), which
is what the mediapipe version pinned in requirements.txt provides — the
older `mp.solutions.hands` API is not available in that version.

Requires a downloaded .task model file (see models/README.md /
scripts/download_model.py). This module never stores or logs camera frames.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("airwheel.vision")

try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import (
        HandLandmarker, HandLandmarkerOptions, RunningMode,
    )
    _MEDIAPIPE_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when mediapipe is missing
    _MEDIAPIPE_AVAILABLE = False


DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "hand_landmarker.task"

# MediaPipe hand landmark indices we care about.
WRIST = 0
INDEX_FINGER_TIP = 8
MIDDLE_FINGER_MCP = 9


@dataclass(frozen=True)
class HandResult:
    handedness: str          # "Left" or "Right" (as reported by MediaPipe, camera-relative)
    landmarks: list[tuple[float, float, float]]  # normalized (x, y, z), 21 points
    confidence: float


@dataclass(frozen=True)
class FrameResult:
    hands: list[HandResult]
    timestamp_ms: int


class HandTracker:
    """Thin, resource-managing wrapper around MediaPipe's HandLandmarker."""

    def __init__(
        self,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        num_hands: int = 2,
        min_hand_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.5,
    ):
        if not _MEDIAPIPE_AVAILABLE:
            raise RuntimeError(
                "mediapipe is not installed. Run: pip install mediapipe"
            )
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Hand landmark model not found at {model_path}. "
                "Run scripts/download_model.py first (see models/README.md)."
            )

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = HandLandmarker.create_from_options(options)
        self._closed = False

    def process(self, frame_rgb: np.ndarray, timestamp_ms: int) -> FrameResult:
        """frame_rgb: HxWx3 uint8 RGB image (NOT stored or logged)."""
        if self._closed:
            raise RuntimeError("HandTracker is closed")
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        hands: list[HandResult] = []
        for i, hand_landmarks in enumerate(result.hand_landmarks or []):
            handedness = "Unknown"
            confidence = 0.0
            if result.handedness and i < len(result.handedness):
                cat = result.handedness[i][0]
                handedness = cat.category_name
                confidence = cat.score
            pts = [(lm.x, lm.y, lm.z) for lm in hand_landmarks]
            hands.append(HandResult(handedness=handedness, landmarks=pts, confidence=confidence))
        return FrameResult(hands=hands, timestamp_ms=timestamp_ms)

    def close(self) -> None:
        if not self._closed:
            self._landmarker.close()
            self._closed = True

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def wrist_point(hand: HandResult) -> tuple[float, float]:
    x, y, _z = hand.landmarks[WRIST]
    return (x, y)


def split_left_right(hands: list[HandResult]) -> tuple[HandResult | None, HandResult | None]:
    """Returns (left_hand, right_hand) by MediaPipe's reported handedness.
    Note: MediaPipe's handedness is from the subject's own perspective, which
    is already mirror-correct for a selfie-view (mirrored) camera preview."""
    left = next((h for h in hands if h.handedness == "Left"), None)
    right = next((h for h in hands if h.handedness == "Right"), None)
    return left, right
