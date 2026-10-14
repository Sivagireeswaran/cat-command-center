"""Feature flags.

Priority (highest first): per-request override > config/flags.local.json > config/flags.default.json
Unknown keys raise KeyError so typos fail loudly.
"""
import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS_PATH = ROOT / "config" / "flags.default.json"
LOCAL_PATH = ROOT / "config" / "flags.local.json"

_request_override: ContextVar = ContextVar("flag_override", default=None)


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _defaults() -> dict:
    return _read(DEFAULTS_PATH)


def _coerce(raw, default):
    """Convert a string override (e.g. from a header) to the default's type."""
    if not isinstance(raw, str):
        return raw
    if isinstance(default, bool):
        return raw.strip().lower() in ("on", "true", "1", "yes")
    if isinstance(default, (int, float)):
        return float(raw)
    return raw.strip()


def all_flags() -> dict:
    merged = _defaults()
    merged.update({k: v for k, v in _read(LOCAL_PATH).items() if k in merged})
    override = _request_override.get()
    if override:
        merged.update(override)
    return merged


def get(key: str):
    flags = all_flags()
    if key not in flags:
        raise KeyError(f"Unknown flag: {key}")
    return flags[key]


def is_on(key: str) -> bool:
    return bool(get(key))


def parse_override(header_value: str) -> dict:
    """Parse 'a=on,b=simulated' into a typed dict, validating keys."""
    defaults = _defaults()
    result = {}
    for part in filter(None, (p.strip() for p in header_value.split(","))):
        key, _, raw = part.partition("=")
        key = key.strip()
        if key not in defaults:
            raise KeyError(f"Unknown flag in override: {key}")
        result[key] = _coerce(raw, defaults[key])
    return result


@contextmanager
def overrides(values: dict):
    """Temporarily override flags (per request or inside a test)."""
    defaults = _defaults()
    for k in values:
        if k not in defaults:
            raise KeyError(f"Unknown flag in override: {k}")
    current = dict(_request_override.get() or {})
    current.update(values)
    token = _request_override.set(current)
    try:
        yield
    finally:
        _request_override.reset(token)


def set_local(key: str, value) -> None:
    """Persist a change (used by the flags panel)."""
    if key not in _defaults():
        raise KeyError(f"Unknown flag: {key}")
    local = _read(LOCAL_PATH)
    local[key] = value
    LOCAL_PATH.write_text(json.dumps(local, indent=2), encoding="utf-8")


def snapshot() -> dict:
    """Store this on every claim and in every log line."""
    return dict(all_flags())


def skipped(key: str) -> dict:
    """Standard result for a check that was turned off. Shows as 'skipped', never 'passed'."""
    return {"ran": False, "skipped_by_flag": key, "result": None, "weight": 0.0}