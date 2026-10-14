"""Process one claim: vision -> authenticity -> recommendation. Policy search and adjuster assignment come later."""
from services.authenticity.scorer import assess
from services.common import flags
from services.dispatch.ranker import severity_of
from services.vision.engine import analyze_building


def _recommend(analysis, auth, severity) -> tuple[str, list[str]]:
    risk = auth["manipulation_risk"]
    if auth["route"] == "manual_review":
        why = "hard flag: " + ", ".join(auth["hard_flags"]) if auth["hard_flags"] \
            else f"manipulation risk {risk} above threshold"
        return "manual_review", [f"Routed to a human: {why}"]
    if analysis.confidence < 0.5:
        return "needs_info", ["Low confidence in the photo analysis; ask the policyholder for more photos"]
    if severity < 0.3 and (risk is None or risk < 0.3):
        return "fast_track", [f"Low damage ({severity}) and low manipulation risk ({risk})"]
    return "standard", [f"Damage {severity}; standard review"]


def process_claim(claim_id, building, event, capture, seen_hashes, created_at, scenario=None, images=None) -> dict:
    analysis = analyze_building(building, images=images, scenario=scenario)
    auth = assess(analysis, building, event, capture, seen_hashes, claim_id, images=images)
    for h in (capture or {}).get("image_hashes", []):
        seen_hashes.setdefault(h, claim_id)

    severity, basis = severity_of(analysis, building.get("band"))
    recommendation, reasoning = _recommend(analysis, auth, severity)
    return {
        "claim_id": claim_id,
        "policy_id": building["policy_id"],
        "building_id": building["building_id"],
        "event_id": event["event_id"],
        "created_at": created_at,
        "status": "triaged",
        "capture_session_id": (capture or {}).get("capture_session_id"),
        "band": building.get("band"),
        "insured_value": building["insured_value"],
        "damage_summary": {"overall_severity": severity, "basis": basis,
                           "elements": [d.model_dump() for d in analysis.damage]},
        "building_analysis": analysis.model_dump(),
        "authenticity": auth,
        "priority_score": None,
        "priority_rank": None,
        "assigned_adjuster_id": None,
        "recommendation": recommendation,
        "requires_human_confirmation": recommendation == "manual_review" or (
            recommendation == "fast_track" and flags.is_on("workflow.human_review_required")),
        "reasoning": reasoning,
        "citations": [],
        "flags_snapshot": flags.snapshot(),
        "human_decision": None,
    }