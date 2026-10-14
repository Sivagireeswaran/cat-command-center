"""Turn hotspots into HazardEvent dicts (see design doc section 3.1).

Notes:
- FIRMS gives satellite hotspot detections, not fire perimeters. Polygons here are buffered footprints.
- The spread cone is a simple downwind heuristic, not a fire-behaviour model. Label it as a projection.
- Wind values are ASSUMED unless you pass real ones (a weather API can be added later).
"""
import math
from datetime import datetime, timezone

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from services.common import flags

SEVERITY_BUFFERS_M = {"extreme": 750, "high": 2500, "moderate": 5000}
CLUSTER_EPS_M = 3000


def _project(lat, lng, lat0, lng0):
    x = (lng - lng0) * 111_320 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 110_540
    return x, y


def _unproject(x, y, lat0, lng0):
    lat = lat0 + y / 110_540
    lng = lng0 + x / (111_320 * math.cos(math.radians(lat0)))
    return lat, lng


def _cluster(points_m: list[tuple[float, float]], eps: float) -> list[list[int]]:
    n = len(points_m)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(points_m[i], points_m[j]) <= eps:
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _to_geojson(geom, lat0, lng0) -> dict:
    if isinstance(geom, MultiPolygon):
        geom = geom.convex_hull
    if not isinstance(geom, Polygon):
        geom = geom.buffer(1)
    ring = [[round(_unproject(x, y, lat0, lng0)[1], 6), round(_unproject(x, y, lat0, lng0)[0], 6)]
            for x, y in geom.exterior.coords]
    return {"type": "Polygon", "coordinates": [ring]}


def _cone(cx, cy, toward_deg, length_m, half_angle=25, steps=8) -> Polygon:
    pts = [(cx, cy)]
    for k in range(steps + 1):
        ang = math.radians(toward_deg - half_angle + k * (2 * half_angle / steps))
        pts.append((cx + length_m * math.sin(ang), cy + length_m * math.cos(ang)))
    return Polygon(pts)


def _detected_at(hotspots: list[dict]) -> str:
    stamps = []
    for h in hotspots:
        d, t = h.get("acq_date"), str(h.get("acq_time") or "").zfill(4)
        if d and len(t) == 4 and t.isdigit():
            stamps.append(f"{d}T{t[:2]}:{t[2:]}:00Z")
    return max(stamps) if stamps else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_fire_events(hotspots: list[dict], source: str,
                      wind_from_deg: float = 45.0, wind_speed_kmh: float = 20.0) -> list[dict]:
    """One HazardEvent per cluster of hotspots. wind_from_deg is meteorological (direction wind comes FROM)."""
    if not hotspots:
        return []
    lat0 = sum(h["lat"] for h in hotspots) / len(hotspots)
    lng0 = sum(h["lng"] for h in hotspots) / len(hotspots)
    pts_m = [_project(h["lat"], h["lng"], lat0, lng0) for h in hotspots]

    use_projection = flags.is_on("hazard.fire.projection")
    toward = (wind_from_deg + 180) % 360
    cone_len_m = min(max(wind_speed_kmh * 250, 2000), 15000)  # heuristic: ~15 min of wind speed, clamped

    events = []
    for idx, members in enumerate(_cluster(pts_m, CLUSTER_EPS_M), start=1):
        cluster_pts = [pts_m[i] for i in members]
        cluster_hs = [hotspots[i] for i in members]
        bands = {name: unary_union([Point(p).buffer(r) for p in cluster_pts])
                 for name, r in SEVERITY_BUFFERS_M.items()}
        cx = sum(p[0] for p in cluster_pts) / len(cluster_pts)
        cy = sum(p[1] for p in cluster_pts) / len(cluster_pts)

        projection = None
        if use_projection:
            cone = _cone(cx, cy, toward, cone_len_m).union(bands["high"])
            projection = {**_to_geojson(cone, lat0, lng0), "basis": "wind_cone"}

        frps = [h["frp"] for h in cluster_hs if h.get("frp") is not None]
        detected_at = _detected_at(cluster_hs)
        events.append({
            "event_id": f"evt_fire_{detected_at[:10].replace('-', '')}_{idx:03d}",
            "hazard_type": "fire",
            "source": source,
            "detected_at": detected_at,
            "geometry": _to_geojson(bands["moderate"], lat0, lng0),
            "projection": projection,
            "severity_bands": [
                {"band": name, "geometry": _to_geojson(bands[name], lat0, lng0)}
                for name in ("extreme", "high", "moderate")
            ],
            "parameters": {
                "wind_speed_kmh": wind_speed_kmh,
                "wind_direction_deg": wind_from_deg,
                "wind_source": "assumed",
                "hotspot_count": len(cluster_hs),
                "max_frp": max(frps) if frps else None,
            },
            "is_simulated": source == "simulated",
        })
    return events