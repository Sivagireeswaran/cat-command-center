from services.common import flags
from services.exposure.query import find_exposed, summarize
from services.hazard.polygon import build_fire_events


def make_event():
    spot = {"lat": 13.10, "lng": 80.10, "acq_date": "2026-10-12", "acq_time": "0630",
            "confidence": "h", "frp": 10.0, "satellite": "N"}
    with flags.overrides({"hazard.fire.projection": False}):
        return build_fire_events([spot], source="firms_cached")[0]


def bld(bid, lat, lng, value=1_000_000):
    return {"building_id": bid, "lat": lat, "lng": lng, "insured_value": value}


def test_bands_and_exclusion():
    event = make_event()
    buildings = [
        bld("at_fire", 13.10, 80.10),      # inside the extreme band
        bld("2km_north", 13.12, 80.10),    # about 2.2 km: inside high, outside extreme
        bld("far_away", 14.10, 80.10),     # far outside the zone
    ]
    with flags.overrides({"exposure.engine": "local"}):
        exposed = find_exposed(event, buildings)
    bands = {b["building_id"]: b["severity_band"] for b in exposed}
    assert bands == {"at_fire": "extreme", "2km_north": "high"}


def test_summary_totals():
    event = make_event()
    buildings = [bld("a", 13.10, 80.10, 5), bld("b", 13.10, 80.1001, 7)]
    with flags.overrides({"exposure.engine": "local"}):
        s = summarize(find_exposed(event, buildings))
    assert s["total_buildings"] == 2 and s["total_insured_value"] == 12
    assert s["by_band"]["extreme"]["count"] == 2