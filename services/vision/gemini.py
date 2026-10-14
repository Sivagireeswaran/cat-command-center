"""Real vision via Gemini on Vertex AI (flag: vision.mode=gemini).

Needs: GCP_PROJECT, GEMINI_MODEL in .env; GCP_REGION (or GEMINI_LOCATION) for the Vertex location.
No silent fallback: if the call fails, it raises.
"""
import io
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from services.common.schemas import BuildingAnalysis, DamageItem, Ornateness
from services.vision import prompts

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

VIEW_ORDER = ["front", "left", "right", "rear", "damage_closeup"]
EXTS = (".jpg", ".jpeg", ".png", ".webp")
MAX_SIDE = 1280
ELEMENTS = {"roof", "facade", "windows", "walls", "other"}


class _DamageOut(BaseModel):
    element: str
    severity: float
    view: str
    evidence: str


class _AnalysisOut(BaseModel):
    construction_type: str
    ornateness_score: float
    ornateness_evidence: list[str]
    damage: list[_DamageOut]
    views_consistent: bool
    consistency_notes: str
    confidence: float


class _ForensicsOut(BaseModel):
    suspicion: float
    findings: list[str]
    confidence: float


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))


def _prepare(data: bytes) -> bytes:
    """Resize and re-encode as JPEG. This strips EXIF: compute image hashes on the ORIGINAL bytes."""
    from PIL import Image
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def load_images(folder) -> list[dict]:
    folder = Path(folder)
    images = []
    for label in VIEW_ORDER:
        for ext in EXTS:
            p = folder / f"{label}{ext}"
            if p.exists():
                images.append({"label": label, "data": _prepare(p.read_bytes()), "mime": "image/jpeg"})
                break
    if len(images) < 2:
        raise FileNotFoundError(
            f"Need at least 2 views in {folder} named {', '.join(VIEW_ORDER)} (.jpg/.png/.webp)")
    return images


def _client():
    from google import genai
    project = os.environ.get("GCP_PROJECT")
    if not project:
        raise RuntimeError("GCP_PROJECT is not set (.env)")
    location = os.environ.get("GEMINI_LOCATION") or os.environ.get("GCP_REGION") or "us-central1"
    try:
        return genai.Client(enterprise=True, project=project, location=location)
    except TypeError:                      # older SDK without the enterprise argument
        return genai.Client(vertexai=True, project=project, location=location)

def _generate(images: list[dict], prompt: str, schema, retries: int = 2):
    from google.genai import types
    model = os.environ.get("GEMINI_MODEL")
    if not model:
        raise RuntimeError("GEMINI_MODEL is not set (.env). Pick a current model ID in Vertex AI Model Garden.")
    contents = []
    for i, img in enumerate(images, start=1):
        contents.append(f"View {i}: {img['label']}")
        contents.append(types.Part.from_bytes(data=img["data"], mime_type=img["mime"]))
    contents.append(prompt)
    cfg = types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json",
                                      response_schema=schema)
    client, last = _client(), None
    for attempt in range(retries + 1):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)
            return schema.model_validate_json(resp.text)
        except Exception as e:  # noqa: BLE001 - surface the final error with context
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gemini call failed after {retries + 1} attempts: {last}") from last


def analyze(building: dict, images: list[dict]) -> BuildingAnalysis:
    prompt = prompts.ANALYSIS_PROMPT.format(recorded_type=building.get("construction_type", "unknown"))
    out = _generate(images, prompt, _AnalysisOut)
    score = _clamp(out.ornateness_score)
    damage = [DamageItem(element=d.element if d.element in ELEMENTS else "other",
                         severity=round(_clamp(d.severity), 2),
                         evidence=f"{d.view}: {d.evidence}") for d in out.damage]
    return BuildingAnalysis(
        construction_type=out.construction_type,
        ornateness=Ornateness(score=round(score, 2), evidence=out.ornateness_evidence),
        replacement_cost_modifier=round(1 + 0.5 * score, 2),   # placeholder heuristic, not insurer-calibrated
        damage=damage,
        views_consistent=out.views_consistent,
        confidence=round(_clamp(out.confidence), 2),
        mode="gemini",
    )


def forensics(images: list[dict]) -> dict:
    out = _generate(images, prompts.FORENSICS_PROMPT, _ForensicsOut)
    return {"risk": round(_clamp(out.suspicion), 2), "findings": out.findings,
            "confidence": round(_clamp(out.confidence), 2)}