"""Vision engine entry point. Behaviour is controlled by flags vision.mode / vision.ornateness / vision.damage."""
from services.common import flags
from services.common.schemas import BuildingAnalysis
from services.vision import mock


def _overall(analysis: BuildingAnalysis) -> float | None:
    if not analysis.damage:
        return 0.0
    sev = [d.severity for d in analysis.damage]
    return round(0.6 * max(sev) + 0.4 * (sum(sev) / len(sev)), 2)


def analyze_building(building: dict, images: list | None = None,
                     scenario: str | None = None) -> BuildingAnalysis:
    mode = flags.get("vision.mode")
    if mode == "mock":
        result = mock.analyze(building, scenario)
    elif mode == "gemini":
        if not images:
            raise ValueError("vision.mode=gemini needs images")
        from services.vision import gemini
        result = gemini.analyze(building, images)
    else:
        raise ValueError(f"Unknown vision.mode: {mode}")

    if not flags.is_on("vision.ornateness"):
        result.ornateness = None
        result.replacement_cost_modifier = 1.0
    if flags.is_on("vision.damage"):
        result.overall_damage = _overall(result)
    else:
        result.damage = []
        result.overall_damage = None
    return result