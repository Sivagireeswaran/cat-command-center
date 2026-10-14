"""Synthetic hazards. Typhoon simulator comes in the next step."""
import random
from datetime import datetime, timezone


def simulate_fire_hotspots(center_lat: float, center_lng: float, n: int = 40,
                           spread_km: float = 3.0, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    out = []
    for _ in range(n):
        out.append({
            "lat": center_lat + rng.gauss(0, spread_km / 111.0 / 2),
            "lng": center_lng + rng.gauss(0, spread_km / 111.0 / 2),
            "acq_date": now.strftime("%Y-%m-%d"),
            "acq_time": now.strftime("%H%M"),
            "confidence": "h",
            "frp": round(rng.uniform(5, 60), 1),
            "satellite": "SIM",
        })
    return out