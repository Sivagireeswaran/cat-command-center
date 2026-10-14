from services.authenticity import checks
from services.authenticity.scorer import assess
from services.common import flags
from services.common.schemas import BuildingAnalysis
from services.hazard.polygon import build_fire_events

B = {"building_id": "B1", "lat": 13.10, "lng": 80.10}
OK = BuildingAnalysis(construction_type="rcc", views_consistent=True, confidence=0.9)
BAD = BuildingAnalysis(construction_type="rcc", views_consistent=False, confidence=0.9)


def event():
    spot = {"lat": 13.10, "lng": 80.10, "acq_date": "2026-10-12", "acq_time": "0630",
            "confidence": "h", "frp": 10.0, "satellite": "N"}
    with flags.overrides({"hazard.fire.projection": False}):
        return build_fire_events([spot], "firms_cached")[0]


def cap(lat=13.10, lng=80.10, captured="2026-10-12T08:00:00Z", received="2026-10-12T08:00:20Z",
        hashes=("h1", "h2")):
    return {"gps": {"lat": lat, "lng": lng, "accuracy_m": 10}, "captured_at_client": captured,
            "received_at_server": received, "image_hashes": list(hashes)}


def test_honest_capture_passes():
    r = assess(OK, B, event(), cap(), {}, "C1")
    assert r["route"] == "pass" and r["manipulation_risk"] < 0.2


def test_far_and_early_capture_flagged():
    r = assess(BAD, B, event(), cap(lat=13.21, captured="2026-10-11T00:00:00Z"), {}, "C1")
    assert r["route"] == "manual_review"


def test_duplicate_is_hard_flag():
    r = assess(OK, B, event(), cap(hashes=("x", "y")), {"x": "C0"}, "C1")
    assert r["route"] == "manual_review" and r["hard_flags"] == ["duplicates"]


def test_check_flag_off_is_skipped_not_passed():
    with flags.overrides({"auth.check.duplicates": False}):
        r = assess(OK, B, event(), cap(hashes=("x",)), {"x": "C0"}, "C1")
    assert r["checks"]["duplicates"]["ran"] is False and r["route"] == "pass"


def test_auth_disabled():
    with flags.overrides({"auth.enabled": False}):
        r = assess(BAD, B, event(), cap(), {}, "C1")
    assert r["manipulation_risk"] is None and r["route"] == "unchecked"


def test_no_capture_data_does_not_count_as_passed():
    r = assess(OK, B, event(), None, {}, "C1")
    assert not r["checks"]["gps_zone"]["ran"] and r["checks"]["cross_angle"]["ran"]


def test_haversine_sanity():
    assert 100 < checks.haversine_m(13.0, 80.0, 13.001, 80.0) < 120