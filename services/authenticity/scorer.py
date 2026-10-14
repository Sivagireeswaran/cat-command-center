"""Combine checks into a manipulation-risk score. Never rejects a claim: routes to manual review."""
from services.authenticity import checks
from services.common import flags


def assess(analysis, building, event, capture, seen_hashes, claim_id, images=None) -> dict:
    if not flags.is_on("auth.enabled"):
        return {"enabled": False, "manipulation_risk": None, "checks": {}, "route": "unchecked",
                "hard_flags": []}

    def run(name, fn):
        key = f"auth.check.{name}"
        return fn() if flags.is_on(key) else flags.skipped(key)

    results = {
        "cross_angle": run("cross_angle", lambda: checks.cross_angle(analysis)),
        "gps_zone": run("gps_zone", lambda: checks.gps_zone(capture, building, event)),
        "time": run("time", lambda: checks.time_after_event(capture, event)),
        "duplicates": run("duplicates", lambda: checks.duplicates(capture, seen_hashes, claim_id)),
        "provenance": run("provenance", lambda: checks.provenance(capture)),
                "visual_forensics": run("visual_forensics",
                                lambda: checks.visual_forensics(images, flags.get("vision.mode"))),
        "synthid": run("synthid", checks.synthid),
    }
    ran = {k: v for k, v in results.items() if v.get("ran")}
    total_w = sum(v["weight"] for v in ran.values())
    risk = round(sum(v["weight"] * v["risk"] for v in ran.values()) / total_w, 3) if total_w else None
    hard = [k for k, v in ran.items() if v.get("hard_flag")]

    if risk is None:
        route = "unchecked"
    elif risk >= flags.get("auth.route_threshold") or hard:
        route = "manual_review"
    else:
        route = "pass"
    return {"enabled": True, "manipulation_risk": risk, "checks": results, "route": route,
            "hard_flags": hard}