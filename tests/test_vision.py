import pytest

from services.common import flags
from services.vision.engine import analyze_building

B = {"building_id": "BLD-1", "year_built": 1960, "construction_type": "masonry", "band": "extreme"}


def test_deterministic():
    assert analyze_building(B).model_dump() == analyze_building(B).model_dump()


def test_severe_worse_than_clean():
    severe = analyze_building(B, scenario="damaged_severe")
    clean = analyze_building(B, scenario="clean")
    assert severe.overall_damage > clean.overall_damage == 0.0


def test_ornateness_flag_off():
    with flags.overrides({"vision.ornateness": False}):
        r = analyze_building(B)
    assert r.ornateness is None and r.replacement_cost_modifier == 1.0


def test_damage_flag_off():
    with flags.overrides({"vision.damage": False}):
        r = analyze_building(B, scenario="damaged_severe")
    assert r.damage == [] and r.overall_damage is None


def test_edited_set_flags_inconsistent_views():
    assert analyze_building(B, scenario="edited").views_consistent is False


def test_gemini_mode_needs_images():
    with flags.overrides({"vision.mode": "gemini"}):
        with pytest.raises(ValueError):
            analyze_building(B)