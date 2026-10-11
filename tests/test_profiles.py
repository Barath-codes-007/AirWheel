import json

import pytest

from app.profiles.manager import BUILTIN_PROFILES, GameProfile, ProfileManager


def test_builtin_profiles_are_valid():
    for p in BUILTIN_PROFILES:
        assert p.validate() == []


def test_default_profile_serialization_roundtrip():
    p = GameProfile(name="My Profile", sensitivity=1.5)
    d = p.to_dict()
    p2 = GameProfile.from_dict(d)
    assert p2 == p


def test_rejects_invalid_sensitivity():
    with pytest.raises(ValueError):
        GameProfile.from_dict({"name": "x", "sensitivity": 99})


def test_rejects_invalid_steering_mode():
    with pytest.raises(ValueError):
        GameProfile.from_dict({"name": "x", "steering_mode": "rm -rf /"})


def test_rejects_bad_name_characters():
    with pytest.raises(ValueError):
        GameProfile.from_dict({"name": "../../etc/passwd"})


def test_unknown_keys_are_ignored_not_executed():
    p = GameProfile.from_dict({
        "name": "Safe",
        "__class__": "os.system",
        "extra_junk": {"a": 1},
    })
    assert p.name == "Safe"


def test_save_load_roundtrip(tmp_path):
    mgr = ProfileManager(tmp_path)
    p = GameProfile(name="Test Profile", max_angle_deg=90)
    assert mgr.save(p)
    loaded = mgr.load("Test Profile")
    assert loaded == p


def test_load_missing_returns_none(tmp_path):
    mgr = ProfileManager(tmp_path)
    assert mgr.load("Nonexistent") is None


def test_load_falls_back_to_builtin(tmp_path):
    mgr = ProfileManager(tmp_path)
    assert mgr.load("Arcade Racing") is not None


def test_list_names_includes_builtins_and_saved(tmp_path):
    mgr = ProfileManager(tmp_path)
    mgr.save(GameProfile(name="Custom One"))
    names = mgr.list_names()
    assert "Custom One" in names
    assert "Default Racing" in names


def test_export_then_import_roundtrip(tmp_path):
    mgr = ProfileManager(tmp_path / "profiles")
    mgr.save(GameProfile(name="Exportable", sensitivity=1.2))
    export_path = tmp_path / "export.json"
    assert mgr.export_all(export_path)

    mgr2 = ProfileManager(tmp_path / "profiles2")
    imported, errors = mgr2.import_file(export_path)
    assert errors == []
    assert any(p.name == "Exportable" for p in imported)


def test_import_rejects_malicious_payload(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"profiles": [
        {"name": "ok"},
        {"name": "bad", "sensitivity": "__import__('os').system('x')"},
        "not even an object",
    ]}), encoding="utf-8")
    mgr = ProfileManager(tmp_path / "profiles")
    imported, errors = mgr.import_file(bad)
    assert len(imported) == 1
    assert len(errors) == 2


def test_import_non_list_root_reports_error(tmp_path):
    bad = tmp_path / "bad2.json"
    bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    mgr = ProfileManager(tmp_path / "profiles")
    imported, errors = mgr.import_file(bad)
    assert imported == []
    assert len(errors) == 1


def test_delete_profile(tmp_path):
    mgr = ProfileManager(tmp_path)
    mgr.save(GameProfile(name="ToDelete"))
    assert mgr.delete("ToDelete") is True
    assert mgr.delete("ToDelete") is False
