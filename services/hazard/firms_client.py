"""NASA FIRMS hotspot client with live / cached / simulated modes (flag: hazard.fire.source)."""
import csv
import io
import json
import logging
import os
from pathlib import Path

import httpx

from services.common import flags

log = logging.getLogger("hazard.firms")

ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = ROOT / "data" / "firms_cache" / "snapshot.json"
BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def _confidence_ok(conf: str) -> bool:
    """VIIRS uses l/n/h, MODIS uses 0-100. Drop low confidence."""
    c = (conf or "").strip().lower()
    if c in ("l", "low"):
        return False
    if c.isdigit():
        return int(c) >= 30
    return True


def parse_csv(text: str, min_confidence: bool = True) -> list[dict]:
    head = text.lstrip()[:200].lower()
    if "latitude" not in head:
        # FIRMS returns plain-text errors (bad key, rate limit) instead of CSV
        raise RuntimeError(f"Unexpected FIRMS response: {text[:150]!r}")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if min_confidence and not _confidence_ok(r.get("confidence", "")):
            continue
        try:
            rows.append({
                "lat": float(r["latitude"]),
                "lng": float(r["longitude"]),
                "acq_date": r.get("acq_date"),
                "acq_time": r.get("acq_time"),
                "confidence": r.get("confidence"),
                "frp": float(r["frp"]) if r.get("frp") else None,
                "satellite": r.get("satellite"),
            })
        except (KeyError, ValueError):
            continue
    return rows


def fetch_live(bbox, days: int = 1, source: str = "VIIRS_SNPP_NRT",
               map_key: str | None = None, timeout: float = 60) -> list[dict]:
    """bbox = (west, south, east, north). Keep it small: a country-sized box returns a lot of rows."""
    map_key = map_key or os.getenv("FIRMS_MAP_KEY")
    if not map_key:
        raise RuntimeError("FIRMS_MAP_KEY is not set (put it in .env)")
    west, south, east, north = bbox
    url = f"{BASE_URL}/{map_key}/{source}/{west},{south},{east},{north}/{days}"
    resp = httpx.get(url, timeout=timeout)  # do not log url: it contains the key
    resp.raise_for_status()
    return parse_csv(resp.text)


def save_snapshot(hotspots: list[dict], meta: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "hotspots": hotspots}, indent=2), encoding="utf-8")


def load_snapshot(path: Path = CACHE_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"No cached snapshot at {path}. Run scripts/fetch_firms.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def get_hotspots(bbox=None, cache_path: Path = CACHE_PATH) -> tuple[list[dict], str]:
    """Return (hotspots, source_label) according to the hazard.fire.source flag.

    live      -> FIRMS API (raises if it fails; no silent fallback, set the flag to 'cached' instead)
    cached    -> stored snapshot
    simulated -> synthetic hotspots around the centre of bbox
    """
    mode = flags.get("hazard.fire.source")
    if mode == "live":
        if bbox is None:
            raise ValueError("bbox is required for live mode")
        return fetch_live(bbox), "firms_live"
    if mode == "cached":
        return load_snapshot(cache_path)["hotspots"], "firms_cached"
    if mode == "simulated":
        from services.hazard.simulator import simulate_fire_hotspots
        if bbox is None:
            raise ValueError("bbox is required for simulated mode")
        west, south, east, north = bbox
        return simulate_fire_hotspots((south + north) / 2, (west + east) / 2), "simulated"
    raise ValueError(f"Unknown hazard.fire.source: {mode}")