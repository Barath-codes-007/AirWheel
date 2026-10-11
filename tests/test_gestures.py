import pytest

from app.vision.gestures import (
    DebouncedEvent, HandPose, classify_hand_pose, count_extended_fingers,
    hands_close_together,
)


def _hand(finger_tip_far=True):
    """21 synthetic landmarks. wrist at origin; MCPs near wrist; tips either
    far (open) or curled back near the MCP (fist)."""
    lm = [(0.0, 0.0, 0.0)] * 21
    lm[0] = (0.5, 0.5, 0.0)  # wrist
    for mcp_idx, tip_idx in [(5, 8), (9, 12), (13, 16), (17, 20)]:
        lm[mcp_idx] = (0.5, 0.4, 0.0)  # knuckle, slightly above wrist
        if finger_tip_far:
            lm[tip_idx] = (0.5, 0.1, 0.0)   # tip far from wrist = extended
        else:
            lm[tip_idx] = (0.5, 0.42, 0.0)  # tip near MCP = curled
    return lm


def test_open_hand_counts_four_extended_fingers():
    assert count_extended_fingers(_hand(finger_tip_far=True)) == 4


def test_fist_counts_zero_extended_fingers():
    assert count_extended_fingers(_hand(finger_tip_far=False)) == 0


def test_classify_open_palm_and_fist():
    assert classify_hand_pose(_hand(True)) == HandPose.OPEN_PALM
    assert classify_hand_pose(_hand(False)) == HandPose.FIST


def test_hands_close_together():
    assert hands_close_together((0.5, 0.5), (0.52, 0.5), reference_separation=0.4) is True
    assert hands_close_together((0.3, 0.5), (0.7, 0.5), reference_separation=0.4) is False


def test_hands_close_together_guards_zero_reference():
    assert hands_close_together((0.5, 0.5), (0.5, 0.5), reference_separation=0.0) is False


def test_debounced_event_requires_sustained_hold():
    ev = DebouncedEvent(hold_seconds=0.3)
    assert ev.update("fist", now=0.0) is None
    assert ev.update("fist", now=0.1) is None
    assert ev.update("fist", now=0.35) == "fist"  # crosses threshold


def test_debounced_event_fires_once_per_hold():
    ev = DebouncedEvent(hold_seconds=0.2)
    ev.update("fist", now=0.0)
    assert ev.update("fist", now=0.25) == "fist"
    assert ev.update("fist", now=0.3) is None  # already confirmed, no repeat


def test_debounced_event_resets_on_change():
    ev = DebouncedEvent(hold_seconds=0.2)
    ev.update("fist", now=0.0)
    assert ev.update("open_palm", now=0.05) is None
    assert ev.update("open_palm", now=0.3) == "open_palm"


def test_debounced_event_noisy_single_frame_never_fires():
    ev = DebouncedEvent(hold_seconds=0.5)
    for i in range(5):
        assert ev.update("fist", now=i * 0.05) is None  # never held long enough
