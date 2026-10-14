"""Deterministic fake vision output. NOT computed from images. For testing the pipeline only."""
import hashlib
import random

from services.common.schemas import BuildingAnalysis, DamageItem, Ornateness

SCENARIOS = ("clean", "damaged_minor", "damaged_severe", "edited")
ORNATE_EVIDENCE = ["carved facade", "domed roof", "decorative columns", "arched windows",
                   "ornamental balconies", "patterned masonry"]
ELEMENTS = ["roof", "facade", "windows", "walls"]


def _rng(building_id: str, scenario: str) -> random.Random:
    digest = hashlib.sha256(f"{building_id}:{scenario}".encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def default_scenario(building: dict) -> str:
    """Pick a scenario from hazard exposure so the demo data tells a coherent story."""
    rng = _rng(building["building_id"], "pick")
    r = rng.random()
    band = building.get("band")
    if band == "extreme":
        return "damaged_severe" if r < 0.6 else "damaged_minor"
    if band == "high":
        return "damaged_minor" if r < 0.6 else ("damaged_severe" if r < 0.8 else "clean")
    if band in ("moderate", "projected"):
        return "damaged_minor" if r < 0.3 else "clean"
    return "clean"


def analyze(building: dict, scenario: str | None = None) -> BuildingAnalysis:
    scenario = scenario or default_scenario(building)
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown mock scenario: {scenario}")
    rng = _rng(building["building_id"], scenario)

    age = 2026 - building.get("year_built", 2000)
    score = 0.2 + age / 200 + (0.2 if building.get("construction_type") == "masonry" else 0.0)
    score = min(max(score + rng.uniform(-0.1, 0.1), 0.0), 1.0)
    n_ev = 0 if score < 0.3 else (1 if score < 0.5 else (2 if score < 0.7 else 3))
    ornateness = Ornateness(score=round(score, 2), evidence=rng.sample(ORNATE_EVIDENCE, n_ev))

    damage = []
    if scenario in ("damaged_minor", "damaged_severe", "edited"):
        count, lo, hi = {"damaged_minor": (rng.randint(1, 2), 0.1, 0.35),
                         "damaged_severe": (rng.randint(3, 4), 0.5, 0.95),
                         "edited": (2, 0.4, 0.7)}[scenario]
        for el in rng.sample(ELEMENTS, count):
            damage.append(DamageItem(element=el, severity=round(rng.uniform(lo, hi), 2),
                                     evidence=f"mock: simulated {el} damage"))

    return BuildingAnalysis(
        construction_type=building.get("construction_type", "unknown"),
        ornateness=ornateness,
        replacement_cost_modifier=round(1 + 0.5 * score, 2),
        damage=damage,
        views_consistent=(scenario != "edited"),
        confidence=0.45 if scenario == "edited" else round(rng.uniform(0.7, 0.9), 2),
        mode="mock",
    )