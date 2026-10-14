import pytest

from services.common import flags
from services.hazard import firms_client
from services.hazard.polygon import build_fire_events

SAMPLE_CSV = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
13.1000,80.1000,330.1,0.4,0.4,2026-10-12,0630,N,VIIRS,h,2.0NRT,295.0,12.5,D
13.1010,80.1010,331.2,0.4,0.4,2026-10-12,0630,N,VIIRS,n,2.0NRT,296.0,8.0,D
13.1020,80.1000,320.0,0.4,0.4,2026-10-12,0630,N,VIIRS,l,2.0NRT,290.0,3.0,D
"""


def hs(lat, lng, frp=10.0):
    return {"lat": lat, "lng": lng, "acq_date": "2026-10-12", "acq_time": "0630",
            "confidence": "h", "frp": frp, "satellite": "N"}


def test_parse_csv_drops_low_confidence():
    rows = firms_client.parse_csv(SAMPLE_CSV)
    assert len(rows) == 2
    assert rows[0]["lat"] == 13.1 and rows[0]["frp"] == 12.5


def test_parse_csv_error_text():
    with pytest.raises(RuntimeError):
        firms_client.parse_csv("Invalid MAP_KEY.")


def test_two_far_clusters_make_two_events():
    spots = [hs(13.10, 80.10), hs(13.101, 80.101), hs(13.30, 80.30), hs(13.301, 80.301)]
    events = build_fire_events(spots, source="firms_cached")
    assert len(events) == 2
    e = events[0]
    for key in ("event_id", "hazard_type", "source", "detected_at", "geometry",
                "severity_bands", "parameters", "is_simulated"):
        assert key in e
    assert [b["band"] for b in e["severity_bands"]] == ["extreme", "high", "moderate"]
    assert e["geometry"]["type"] == "Polygon"


def test_projection_flag():
    spots = [hs(13.10, 80.10), hs(13.101, 80.101)]
    with flags.overrides({"hazard.fire.projection": True}):
        assert build_fire_events(spots, "firms_cached")[0]["projection"] is not None
    with flags.overrides({"hazard.fire.projection": False}):
        assert build_fire_events(spots, "firms_cached")[0]["projection"] is None


def test_cached_and_simulated_modes(tmp_path):
    path = tmp_path / "snap.json"
    firms_client.save_snapshot([hs(13.1, 80.1)], {"test": True}, path)
    with flags.overrides({"hazard.fire.source": "cached"}):
        spots, label = firms_client.get_hotspots(cache_path=path)
        assert label == "firms_cached" and len(spots) == 1
    with flags.overrides({"hazard.fire.source": "simulated"}):
        spots, label = firms_client.get_hotspots(bbox=(80.0, 13.0, 80.2, 13.2))
        assert label == "simulated" and len(spots) > 0
        assert build_fire_events(spots, label)[0]["is_simulated"] is True