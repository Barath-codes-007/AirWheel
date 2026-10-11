import json
import logging

from app.config import AppSettings, load_settings, save_settings
from app.utils.logging_setup import setup_logging


def test_defaults_match_spec():
    s = AppSettings()
    assert s.steering.mode == "two_hand"
    assert s.steering.max_angle_deg == 60.0
    assert s.steering.sensitivity == 1.0
    assert s.ui.theme == "dark"
    assert s.ui.debug_mode is False
    assert s.log_level == "INFO"
    assert s.output.emergency_stop_hotkey == "F12"


def test_roundtrip(tmp_path):
    p = tmp_path / "settings.json"
    s = AppSettings()
    s.steering.max_angle_deg = 90.0
    s.steering.calibrated_center_deg = -12.5
    s.camera.device_index = 2
    assert save_settings(s, p)
    loaded = load_settings(p)
    assert loaded.to_dict() == s.to_dict()


def test_missing_file_gives_defaults(tmp_path):
    assert load_settings(tmp_path / "nope.json").to_dict() == AppSettings().to_dict()


def test_corrupt_file_gives_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ not json", encoding="utf-8")
    assert load_settings(p).to_dict() == AppSettings().to_dict()


def test_non_object_root_gives_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_settings(p).to_dict() == AppSettings().to_dict()


def test_wrong_types_and_unknown_keys_are_ignored(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({
        "evil": "__import__('os').system('x')",
        "steering": {"max_angle_deg": "huge", "deadzone_pct": 5, "bogus": 1},
        "camera": {"width": True},
    }), encoding="utf-8")
    s = load_settings(p)
    assert s.steering.max_angle_deg == 60.0   # bad type rejected
    assert s.steering.deadzone_pct == 5       # int accepted for float field
    assert s.camera.width == 1280             # bool rejected for int field


def test_partial_file_keeps_other_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"steering": {"invert": True}}), encoding="utf-8")
    s = load_settings(p)
    assert s.steering.invert is True
    assert s.steering.max_angle_deg == 60.0


def test_logging_setup_is_idempotent(tmp_path):
    setup_logging("DEBUG", tmp_path)
    logger = setup_logging("INFO", tmp_path)
    assert len(logger.handlers) == 2
    assert logger.level == logging.INFO
    assert (tmp_path / "airwheel.log").exists()
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()


def test_phase9_defaults_are_off_by_default():
    s = AppSettings()
    assert s.overlay.enabled is False
    assert s.pedals.throttle_mode == "off"
    assert s.pedals.brake_mode == "off"
    assert s.gestures.enabled is False
    assert s.gestures.recenter_gesture_enabled is False


def test_phase9_settings_roundtrip(tmp_path):
    p = tmp_path / "settings.json"
    s = AppSettings()
    s.overlay.enabled = True
    s.overlay.opacity = 0.5
    s.pedals.throttle_mode = "virtual_axis"
    s.gestures.enabled = True
    assert save_settings(s, p)
    loaded = load_settings(p)
    assert loaded.to_dict() == s.to_dict()
