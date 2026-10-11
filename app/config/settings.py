"""Persistent application settings (JSON). No camera frames are ever stored."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from app.utils.paths import config_path

log = logging.getLogger("airwheel.config")

SCHEMA_VERSION = 1


@dataclass
class CameraSettings:
    device_index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    mirror_preview: bool = True


@dataclass
class SteeringSettings:
    mode: str = "two_hand"          # "two_hand" | "one_hand" (experimental)
    max_angle_deg: float = 60.0
    sensitivity: float = 1.0        # 0.5 - 2.0
    deadzone_pct: float = 2.0       # 0 - 10
    smoothing: str = "medium"       # "low" | "medium" | "high"
    response_curve: str = "linear"  # "linear" | "progressive" | "soft" | "aggressive"
    invert: bool = False
    center_return: str = "smooth"   # "instant" | "fast" | "smooth"
    calibrated_center_deg: float | None = None


@dataclass
class OutputSettings:
    backend: str = "virtual_gamepad"  # "virtual_gamepad" | "keyboard"
    emergency_stop_hotkey: str = "F12"
    toggle_hotkey: str = "ctrl+shift+a"


@dataclass
class UISettings:
    theme: str = "dark"
    font_size: int = 10
    advanced_mode: bool = False
    show_landmarks: bool = True
    debug_mode: bool = False


@dataclass
class OverlaySettings:
    """Phase 9 (spec sections 27, 93). Overlay is opt-in via Game Mode."""
    enabled: bool = False
    opacity: float = 0.85
    pos_x: int = 40
    pos_y: int = 40
    width: int = 220
    height: int = 120
    show_status: bool = True
    show_steering: bool = True
    show_tracking: bool = True
    show_controller: bool = True


@dataclass
class PedalSettings:
    """Phase 9 (spec sections 18, 19, 87, 88). OFF by default - never
    enabled unless the user explicitly turns a pedal on."""
    throttle_mode: str = "off"  # "off" | "gesture" | "keyboard" | "virtual_axis"
    brake_mode: str = "off"
    smoothing: str = "medium"
    deadzone_pct: float = 2.0


@dataclass
class GestureSettings:
    """Phase 9 (spec sections 20, 29, 92). Disabled by default."""
    enabled: bool = False
    hold_seconds: float = 0.4
    recenter_gesture_enabled: bool = False


@dataclass
class AppSettings:
    schema_version: int = SCHEMA_VERSION
    active_profile: str = "Default Racing"
    log_level: str = "INFO"
    camera: CameraSettings = field(default_factory=CameraSettings)
    steering: SteeringSettings = field(default_factory=SteeringSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    ui: UISettings = field(default_factory=UISettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    pedals: PedalSettings = field(default_factory=PedalSettings)
    gestures: GestureSettings = field(default_factory=GestureSettings)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        """Build settings from untrusted data: unknown keys are ignored and
        wrongly-typed values fall back to defaults."""
        if not isinstance(data, dict):
            raise ValueError("settings root must be a JSON object")
        base = cls()
        for f in fields(cls):
            if f.name not in data:
                continue
            current = getattr(base, f.name)
            value = data[f.name]
            if hasattr(current, "__dataclass_fields__"):
                setattr(base, f.name, _merge_dataclass(current, value))
            elif _type_ok(current, value):
                setattr(base, f.name, value)
            else:
                log.warning("Ignoring invalid value for %s", f.name)
        return base


def _type_ok(default: Any, value: Any) -> bool:
    if default is None:
        return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


def _merge_dataclass(instance: Any, data: Any) -> Any:
    if not isinstance(data, dict):
        log.warning("Ignoring invalid section for %s", type(instance).__name__)
        return instance
    for f in fields(instance):
        if f.name in data:
            default = getattr(instance, f.name)
            # calibrated_center_deg defaults to None, so accept numbers or None there.
            ok = _type_ok(default, data[f.name])
            if ok:
                setattr(instance, f.name, data[f.name])
            else:
                log.warning("Ignoring invalid value for %s.%s", type(instance).__name__, f.name)
    return instance


def load_settings(path: Path | None = None) -> AppSettings:
    """Load settings; a missing or corrupt file yields defaults (never crashes)."""
    path = Path(path) if path else config_path()
    if not path.exists():
        log.info("No settings file yet; using defaults")
        return AppSettings()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return AppSettings.from_dict(json.load(fh))
    except (OSError, ValueError) as exc:
        log.error("Could not read settings (%s); using defaults", exc)
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> bool:
    """Atomically write settings so a crash can't leave a half-written file."""
    path = Path(path) if path else config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, indent=2)
        os.replace(tmp, path)
        return True
    except OSError as exc:
        log.error("Could not save settings: %s", exc)
        return False
