"""Game profiles: storage, validation, import/export (spec sections 16, 17,
83-86). Profile JSON is untrusted input when imported - never executed,
strictly validated.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from app.utils.paths import profiles_dir

log = logging.getLogger("airwheel.profiles")

_VALID_STEERING_MODES = {"virtual_axis", "keyboard"}
_VALID_PEDAL_MODES = {"off", "gesture", "keyboard", "virtual_axis"}
_NAME_RE = re.compile(r"^[A-Za-z0-9 _\-\.]{1,50}$")


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


@dataclass
class GameProfile:
    name: str = "Default Racing"
    steering_mode: str = "virtual_axis"       # "virtual_axis" | "keyboard"
    sensitivity: float = 1.0
    max_angle_deg: float = 60.0
    deadzone_pct: float = 2.0
    smoothing: str = "medium"
    response_curve: str = "linear"
    invert_steering: bool = False
    throttle_mode: str = "off"                # off | gesture | keyboard | virtual_axis
    brake_mode: str = "off"
    handbrake_key: str = "space"
    throttle_key: str = "w"
    brake_key: str = "s"

    def validate(self) -> list[str]:
        """Returns a list of problems; empty list means valid."""
        problems: list[str] = []
        if not _NAME_RE.match(self.name or ""):
            problems.append("name must be 1-50 chars: letters, numbers, space, _-.")
        if self.steering_mode not in _VALID_STEERING_MODES:
            problems.append(f"invalid steering_mode: {self.steering_mode!r}")
        if self.throttle_mode not in _VALID_PEDAL_MODES:
            problems.append(f"invalid throttle_mode: {self.throttle_mode!r}")
        if self.brake_mode not in _VALID_PEDAL_MODES:
            problems.append(f"invalid brake_mode: {self.brake_mode!r}")
        if not _is_number(self.sensitivity) or not (0.5 <= self.sensitivity <= 2.0):
            problems.append("sensitivity must be a number between 0.5 and 2.0")
        if not _is_number(self.max_angle_deg) or not (10.0 <= self.max_angle_deg <= 180.0):
            problems.append("max_angle_deg must be a number between 10 and 180")
        if not _is_number(self.deadzone_pct) or not (0.0 <= self.deadzone_pct <= 10.0):
            problems.append("deadzone_pct must be a number between 0 and 10")
        if self.smoothing not in ("low", "medium", "high"):
            problems.append(f"invalid smoothing: {self.smoothing!r}")
        if self.response_curve not in ("linear", "progressive", "soft", "aggressive"):
            problems.append(f"invalid response_curve: {self.response_curve!r}")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameProfile":
        if not isinstance(data, dict):
            raise ValueError("profile must be a JSON object")
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        profile = cls(**{**cls().to_dict(), **filtered})
        problems = profile.validate()
        if problems:
            raise ValueError("invalid profile: " + "; ".join(problems))
        return profile


BUILTIN_PROFILES: list[GameProfile] = [
    GameProfile(name="Default Racing"),
    GameProfile(name="Arcade Racing", response_curve="progressive", sensitivity=1.3),
    GameProfile(name="Truck Simulator", max_angle_deg=90, response_curve="soft", smoothing="high"),
    GameProfile(name="Formula Racing", max_angle_deg=45, response_curve="aggressive", smoothing="low"),
    GameProfile(name="Keyboard Racing", steering_mode="keyboard"),
]


class ProfileManager:
    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory) if directory else profiles_dir()

    def _path_for(self, name: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_") or "profile"
        return self.directory / f"{safe}.json"

    def save(self, profile: GameProfile) -> bool:
        problems = profile.validate()
        if problems:
            log.error("Refusing to save invalid profile %s: %s", profile.name, problems)
            return False
        path = self._path_for(profile.name)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(profile.to_dict(), fh, indent=2)
            os.replace(tmp, path)
            return True
        except OSError as exc:
            log.error("Could not save profile %s: %s", profile.name, exc)
            return False

    def load(self, name: str) -> GameProfile | None:
        path = self._path_for(name)
        if not path.exists():
            builtin = next((p for p in BUILTIN_PROFILES if p.name == name), None)
            return builtin
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return GameProfile.from_dict(json.load(fh))
        except (OSError, ValueError) as exc:
            log.error("Could not load profile %s: %s", name, exc)
            return None

    def list_names(self) -> list[str]:
        names = {p.name for p in BUILTIN_PROFILES}
        if self.directory.exists():
            for path in self.directory.glob("*.json"):
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    if isinstance(data, dict) and isinstance(data.get("name"), str):
                        names.add(data["name"])
                except (OSError, ValueError):
                    continue
        return sorted(names)

    def delete(self, name: str) -> bool:
        path = self._path_for(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def export_all(self, dest: Path) -> bool:
        data = []
        for name in self.list_names():
            p = self.load(name)
            if p:
                data.append(p.to_dict())
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                json.dump({"profiles": data}, fh, indent=2)
            return True
        except OSError as exc:
            log.error("Could not export profiles: %s", exc)
            return False

    def import_file(self, src: Path) -> tuple[list[GameProfile], list[str]]:
        """Returns (imported_profiles, error_messages). Never executes code
        from the file; every profile is revalidated."""
        imported: list[GameProfile] = []
        errors: list[str] = []
        try:
            with open(src, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            return [], [f"could not read {src}: {exc}"]

        candidates = data.get("profiles") if isinstance(data, dict) else data
        if not isinstance(candidates, list):
            return [], ["import file must contain a list of profiles (or {'profiles': [...]})"]

        for i, raw in enumerate(candidates):
            try:
                profile = GameProfile.from_dict(raw)
                if self.save(profile):
                    imported.append(profile)
                else:
                    errors.append(f"profile {i}: failed to save")
            except ValueError as exc:
                errors.append(f"profile {i}: {exc}")
        return imported, errors
