from services.common import flags
from services.hazard.polygon import build_fire_events
from services.orchestrator.pipeline import process_claim

B = {"building_id": "BLD-9", "policy_id": "POL-9", "lat": 13.10, "lng": 80.10, "year_built": 1980,
     "construction_type": "rcc", "insured_value": 1000, "band": "extreme"}


def event():
    spot = {"lat": 13.10, "lng": 80.10, "acq_date": "2026-10-12", "acq_time": "0630",
            "confidence": "h", "frp": 10.0, "satellite": "N"}
    with flags.overrides({"hazard.fire.projection": False}):
        return build_fire_events([spot], "firms_cached")[0]


def capture(**kw):
    c = {"capture_session_id": "cap_1", "gps": {"lat": 13.10, "lng": 80.10, "accuracy_m": 10},
         "captured_at_client": "2026-10-12T08:00:00Z", "received_at_server": "2026-10-12T08:00:20Z",
         "image_hashes": ["a", "b", "c", "d", "e"]}
    c.update(kw)
    return c


def test_clean_claim_is_not_flagged():
    c = process_claim("C1", B, event(), capture(), {}, "2026-10-12T08:00:20Z", scenario="clean")
    assert c["recommendation"] == "fast_track" and c["requires_human_confirmation"] is True
    assert c["flags_snapshot"]["vision.mode"] == "mock"


def test_severe_claim_is_standard():
    c = process_claim("C2", B, event(), capture(), {}, "t", scenario="damaged_severe")
    assert c["recommendation"] == "standard" and c["damage_summary"]["overall_severity"] > 0.5


def test_edited_set_goes_to_manual_review():
    cap = capture(gps={"lat": 13.21, "lng": 80.10, "accuracy_m": 10},
                  captured_at_client="2026-10-10T20:00:00Z")
    c = process_claim("C3", B, event(), cap, {}, "t", scenario="edited")
    assert c["recommendation"] == "manual_review"


def test_auth_off_lets_the_same_claim_through():
    cap = capture(gps={"lat": 13.21, "lng": 80.10, "accuracy_m": 10},
                  captured_at_client="2026-10-10T20:00:00Z")
    with flags.overrides({"auth.enabled": False}):
        c = process_claim("C3", B, event(), cap, {}, "t", scenario="edited")
    assert c["recommendation"] != "manual_review" and c["authenticity"]["route"] == "unchecked"