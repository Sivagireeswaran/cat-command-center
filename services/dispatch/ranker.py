"""Rank claims. Mode comes from flag dispatch.priority_mode: severity_exposure | severity_only | fifo."""
from services.common import flags

BAND_WEIGHT = {"extreme": 1.0, "high": 0.75, "moderate": 0.5, "projected": 0.25}


def severity_of(analysis, band) -> tuple[float, str]:
    if analysis.overall_damage is not None:
        return analysis.overall_damage, "vision"
    return BAND_WEIGHT.get(band, 0.1), "hazard_band"


def rank(claims: list[dict]) -> list[dict]:
    mode = flags.get("dispatch.priority_mode")
    if mode == "fifo":
        ordered = sorted(claims, key=lambda c: (c["created_at"], c["claim_id"]))
        for c in ordered:
            c["priority_score"] = 0.0
    elif mode in ("severity_only", "severity_exposure"):
        max_val = max((c["insured_value"] for c in claims), default=1) or 1
        for c in claims:
            sev = c["damage_summary"]["overall_severity"]
            if mode == "severity_only":
                score = sev
            else:
                risk = c["authenticity"].get("manipulation_risk")
                auth_factor = 1.0 if risk is None else 1 - 0.6 * risk   # suspicious claims drop in queue, never blocked
                score = sev * (0.5 + 0.5 * c["insured_value"] / max_val) * auth_factor
            c["priority_score"] = round(score, 4)
        ordered = sorted(claims, key=lambda c: (-c["priority_score"], c["created_at"], c["claim_id"]))
    else:
        raise ValueError(f"Unknown dispatch.priority_mode: {mode}")
    for i, c in enumerate(ordered, start=1):
        c["priority_rank"] = i
    return ordered