import pytest
from shapely.geometry import shape

from services.common import flags
from services.exposure.query import find_exposed
from services.hazard.typhoon import simulate_typhoon


def test_bands_nested_and_labeled():
    e = simulate_typhoon(13.5, 100.5, "typhoon_a")
    g = {b["band"]: shape(b["geometry"]) for b in e["severity_bands"]}
    assert g["high"].contains(g["extreme"]) and g["moderate"].contains(g["high"])
    assert e["hazard_type"] == "typhoon" and e["is_simulated"] is True
    assert e["projection"]["basis"] == "storm_track"


def test_unknown_scenario():
    with pytest.raises(ValueError):
        simulate_typhoon(13.5, 100.5, "nope")


def test_exposure_on_track():
    e = simulate_typhoon(13.5, 100.5, "typhoon_a")
    land = e["parameters"]["landfall"]
    on = {"building_id": "on", "lat": land["lat"], "lng": land["lng"], "insured_value": 1}
    far = {"building_id": "far", "lat": 20.0, "lng": 110.0, "insured_value": 1}
    with flags.overrides({"exposure.engine": "local"}):
        res = find_exposed(e, [on, far])
    assert [r["building_id"] for r in res] == ["on"] and res[0]["severity_band"] == "extreme"