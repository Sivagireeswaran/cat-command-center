"""Simulated typhoon: stylised wind bands along a straight track. Everything here is synthetic.

Radii are demo-scale (city/region), not meteorological. Label the output as simulated in the UI.
"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import LineString

from services.hazard.polygon import _project, _to_geojson, _unproject

ROOT = Path(__file__).resolve().parents[2]

# landfall_offset = (dlat, dlng) from the centre you pass in (usually the fire centre)
SCENARIOS = {
    "typhoon_a": {"name": "Typhoon A", "landfall_offset": (-0.30, 0.25),
                  "heading_deg": 300, "max_wind_kmh": 165, "forward_speed_kmh": 20},
    "typhoon_b": {"name": "Typhoon B", "landfall_offset": (0.25, -0.25),
                  "heading_deg": 270, "max_wind_kmh": 120, "forward_speed_kmh": 15},
}

BAND_KM = {"extreme": 8, "high": 20, "moderate": 40}   # at wind factor 1.0 (150 km/h)
HALF_TRACK_KM = 80


def _scenario(name: str) -> dict:
    if name == "custom":
        path = ROOT / "data" / "fixtures" / "typhoon_custom.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Create {path} with keys: name, landfall_offset [dlat, dlng], "
                "heading_deg, max_wind_kmh, forward_speed_kmh")
        return json.loads(path.read_text(encoding="utf-8"))
    if name not in SCENARIOS:
        raise ValueError(f"Unknown typhoon scenario: {name}")
    return SCENARIOS[name]


def simulate_typhoon(center_lat: float, center_lng: float, scenario: str = "typhoon_a") -> dict:
    sc = _scenario(scenario)
    lat0 = center_lat + sc["landfall_offset"][0]
    lng0 = center_lng + sc["landfall_offset"][1]

    h = math.radians(sc["heading_deg"])
    dx, dy = math.sin(h), math.cos(h)
    half = HALF_TRACK_KM * 1000
    start, end = (-dx * half, -dy * half), (dx * half, dy * half)
    full = LineString([start, end])
    ahead = LineString([(0, 0), end])

    factor = min(max(sc["max_wind_kmh"] / 150, 0.6), 1.4)
    radius = {k: v * 1000 * factor for k, v in BAND_KM.items()}

    track = [[round(_unproject(*p, lat0, lng0)[1], 5), round(_unproject(*p, lat0, lng0)[0], 5)]
             for p in (start, (0, 0), end)]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "event_id": f"evt_typhoon_{scenario}",
        "hazard_type": "typhoon",
        "source": "simulated",
        "detected_at": now,
        "geometry": _to_geojson(full.buffer(radius["moderate"]), lat0, lng0),
        "projection": {**_to_geojson(ahead.buffer(radius["moderate"] * 1.3), lat0, lng0),
                       "basis": "storm_track"},
        "severity_bands": [
            {"band": name, "geometry": _to_geojson(full.buffer(radius[name]), lat0, lng0)}
            for name in ("extreme", "high", "moderate")
        ],
        "parameters": {
            "scenario": scenario, "name": sc["name"],
            "max_wind_kmh": sc["max_wind_kmh"], "forward_speed_kmh": sc["forward_speed_kmh"],
            "heading_deg": sc["heading_deg"], "landfall": {"lat": lat0, "lng": lng0},
            "track": track,
        },
        "is_simulated": True,
    }