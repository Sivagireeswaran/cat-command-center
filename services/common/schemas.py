from typing import Literal, Optional

from pydantic import BaseModel, Field

Element = Literal["roof", "facade", "windows", "walls", "other"]


class DamageItem(BaseModel):
    element: Element
    severity: float = Field(ge=0, le=1)
    evidence: str


class Ornateness(BaseModel):
    score: float = Field(ge=0, le=1)
    evidence: list[str]


class BuildingAnalysis(BaseModel):
    construction_type: str
    ornateness: Optional[Ornateness] = None
    replacement_cost_modifier: float = 1.0
    damage: list[DamageItem] = []
    overall_damage: Optional[float] = None
    views_consistent: bool = True
    confidence: float = Field(default=0.5, ge=0, le=1)
    mode: str = "mock"   # mock | gemini