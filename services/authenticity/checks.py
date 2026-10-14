"""Individual authenticity checks.

Each returns a dict: ran, risk (0 = fine, 1 = suspicious), result, weight.
A check that cannot run (no data, detector not wired) returns ran=False and never counts as 'passed'.
"""
import math
from datetime import datetime

from shapely.geometry import Point, shape

WEIGHTS = {"cross_angle": 0.25, "gps_zone": 0.20, "time": 0.15, "duplicates": 0.25,
           "provenance": 0.10, "visual_forensics": 0.15, "synthid": 0.05}


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _ran(name, risk, detail, hard=False):
    return {"ran": True, "risk": round(risk, 2), "result": detail,
            "weight": WEIGHTS[name], "hard_flag": hard}


def no_data(why: str) -> dict:
    return {"ran": False, "skipped_by_flag": None, "result": f"not run: {why}", "weight": 0.0}


def cross_angle(analysis) -> dict:
    if not analysis.views_consistent:
        return _ran("cross_angle", 0.9, "views do not look like the same building")
    if analysis.confidence < 0.5:
        return _ran("cross_angle", 0.5, "low confidence in view consistency")
    return _ran("cross_angle", 0.05, "views consistent")


def gps_zone(capture, building, event) -> dict:
    if not capture or not capture.get("gps"):
        return no_data("no capture GPS")
    g = capture["gps"]
    d = haversine_m(g["lat"], g["lng"], building["lat"], building["lng"])
    risk, notes = 0.05, []
    if d > 150 + g.get("accuracy_m", 0):
        risk = 0.4 if d <= 1000 else 0.9
        notes.append(f"{d:.0f} m from insured address")
    pt = Point(g["lng"], g["lat"])
    in_zone = shape(event["geometry"]).covers(pt) or (
        bool(event.get("projection")) and shape(event["projection"]).covers(pt))
    if not in_zone:
        risk = max(risk, 0.8)
        notes.append("capture location outside hazard zone")
    return _ran("gps_zone", risk, "; ".join(notes) or "at insured address, inside hazard zone")


def time_after_event(capture, event) -> dict:
    if not capture or not capture.get("captured_at_client") or not capture.get("received_at_server"):
        return no_data("no capture timestamps")
    cap = parse_ts(capture["captured_at_client"])
    recv = parse_ts(capture["received_at_server"])
    start = parse_ts(event["detected_at"])
    skew_min = abs((recv - cap).total_seconds()) / 60
    risk, notes = 0.05, []
    if cap < start:
        risk = 0.9
        notes.append("captured before the event started")
    if skew_min > 10:
        risk = max(risk, 0.6)
        notes.append(f"device clock differs from server by {skew_min:.0f} min")
    return _ran("time", risk, "; ".join(notes) or "captured after event, clock consistent")


def duplicates(capture, seen_hashes, claim_id) -> dict:
    hashes = (capture or {}).get("image_hashes")
    if not hashes:
        return no_data("no image hashes")
    other = {seen_hashes[h] for h in hashes if h in seen_hashes and seen_hashes[h] != claim_id}
    if other:
        return _ran("duplicates", 0.95, f"identical image(s) already used in {sorted(other)}", hard=True)
    return _ran("duplicates", 0.05, "no reuse found")


def provenance(capture) -> dict:
    return no_data("EXIF/content-credential reader not wired (web canvas capture strips EXIF)")

def visual_forensics(images, vision_mode) -> dict:
    if vision_mode != "gemini":
        return no_data("needs vision.mode=gemini")
    if not images:
        return no_data("no images supplied")
    from services.vision import gemini
    out = gemini.forensics(images)
    detail = "; ".join(out["findings"]) or "no manipulation signs reported"
    return _ran("visual_forensics", out["risk"], f"{detail} (model confidence {out['confidence']})")

def synthid() -> dict:
    return no_data("detector not wired; a clean result would not prove anything anyway")