from services.common import flags
from services.dispatch.ranker import rank


def claim(cid, sev, value, created, risk=None):
    return {"claim_id": cid, "created_at": created, "insured_value": value,
            "damage_summary": {"overall_severity": sev},
            "authenticity": {"manipulation_risk": risk}}


CLAIMS = lambda: [claim("a", 0.2, 100, "2026-10-12T01:00:00Z"),
                  claim("b", 0.9, 100, "2026-10-12T02:00:00Z"),
                  claim("c", 0.9, 100, "2026-10-12T03:00:00Z", risk=0.9)]


def test_fifo_is_arrival_order():
    with flags.overrides({"dispatch.priority_mode": "fifo"}):
        assert [c["claim_id"] for c in rank(CLAIMS())] == ["a", "b", "c"]


def test_severity_first_and_suspicious_drops():
    with flags.overrides({"dispatch.priority_mode": "severity_exposure"}):
        assert [c["claim_id"] for c in rank(CLAIMS())] == ["b", "c", "a"]


def test_exposure_breaks_ties():
    cs = [claim("small", 0.5, 100, "t1"), claim("big", 0.5, 1000, "t2")]
    with flags.overrides({"dispatch.priority_mode": "severity_exposure"}):
        assert rank(cs)[0]["claim_id"] == "big"
    cs = [claim("small", 0.5, 100, "t1"), claim("big", 0.5, 1000, "t2")]
    with flags.overrides({"dispatch.priority_mode": "severity_only"}):
        assert rank(cs)[0]["claim_id"] == "small"   # tie broken by arrival time