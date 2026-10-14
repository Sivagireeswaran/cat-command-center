import pytest
from services.common import flags


def test_defaults_load():
    assert flags.get("vision.mode") == "mock"
    assert flags.is_on("auth.enabled") is True


def test_override_context():
    with flags.overrides({"auth.enabled": False}):
        assert flags.is_on("auth.enabled") is False
    assert flags.is_on("auth.enabled") is True


def test_header_parsing_types():
    parsed = flags.parse_override("auth.enabled=off,auth.route_threshold=0.8,vision.mode=gemini")
    assert parsed == {"auth.enabled": False, "auth.route_threshold": 0.8, "vision.mode": "gemini"}


def test_unknown_flag_fails():
    with pytest.raises(KeyError):
        flags.get("does.not.exist")


def test_skipped_shape():
    s = flags.skipped("auth.check.time")
    assert s["ran"] is False and s["weight"] == 0.0