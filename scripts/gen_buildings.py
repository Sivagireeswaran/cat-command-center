"""Generate a synthetic insured-building portfolio around the hazard events.

Usage (from project root, venv active):
  python scripts/gen_buildings.py --n 200
Writes data/buildings/buildings.json and buildings.csv (all data is fictional).
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path
from global_land_mask import globe  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shapely.geometry import Point, shape  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from services.hazard.polygon import build_fire_events  # noqa: E402
from services.hazard.simulator import simulate_fire_hotspots  # noqa: E402

CONSTRUCTION = ["masonry", "wood", "rcc", "steel", "mixed"]
CONSTRUCTION_W = [0.30, 0.10, 0.40, 0.08, 0.12]
NEAR_DEG = 0.07   # about 7-8 km
FAR_DEG = 0.30


def load_events(center):
    p = ROOT / "data" / "fixtures" / "hazard_events.json"
    if p.exists():
        print(f"Using events from {p}")
        return json.loads(p.read_text(encoding="utf-8"))
    print("No hazard_events.json found; using a simulated fire")
    return build_fire_events(simulate_fire_hotspots(*center), source="simulated")


def sample_point(rng, region, attempts=5000):
    polys = [g for g in getattr(region, "geoms", [region]) if g.area > 0]
    if not polys:
        raise RuntimeError("Region is empty")
    for _ in range(attempts):
        poly = rng.choices(polys, weights=[g.area for g in polys])[0]
        minx, miny, maxx, maxy = poly.bounds
        p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if poly.contains(p) and globe.is_land(p.y, p.x):
            return p
    raise RuntimeError("Could not sample a point in region")


def build_regions(event):
    bands = {b["band"]: shape(b["geometry"]) for b in event["severity_bands"]}
    extreme, high, moderate = bands["extreme"], bands["high"], bands["moderate"]
    return {
        "extreme": extreme,
        "high": high.difference(extreme),
        "moderate": moderate.difference(high),
        "near": moderate.buffer(NEAR_DEG).difference(moderate),
    }


def make_building(rng, i, p):
    value = round(rng.uniform(2_000_000, 50_000_000), -4)
    return {
        "policy_id": f"POL-{10000 + i}",
        "building_id": f"BLD-{7000 + i}",
        "address": f"Plot {rng.randint(1, 400)}, Sector {rng.randint(1, 30)}, Demo Town",
        "lat": round(p.y, 6),
        "lng": round(p.x, 6),
        "construction_type": rng.choices(CONSTRUCTION, CONSTRUCTION_W)[0],
        "year_built": rng.randint(1950, 2022),
        "storeys": rng.randint(1, 6),
        "insured_value": value,  # arbitrary currency units
        "ornateness_score_baseline": None,
        "hazard_risk_score": None,
        "policy_document_id": f"doc_policy_{rng.randint(1, 2)}",
        "sub_limits": {"contents": round(value * 0.2, -3), "rebuild_modifier_cap": 1.5},
        "deductible": round(value * 0.02, -2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--center", default="14.0,100.5", help="lat,lng used only if no events file exists")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    center = tuple(float(v) for v in args.center.split(","))
    events = load_events(center)

    buildings, i = [], 0
    budget = args.n * 0.6 / len(events)          # 60% of buildings split evenly across events
    for e in events:
        regions = build_regions(e)
        for name, share in [("extreme", 0.2), ("high", 0.3), ("moderate", 0.3), ("near", 0.2)]:
            for _ in range(round(budget * share)):
                i += 1
                buildings.append(make_building(rng, i, sample_point(rng, regions[name])))

    zone = unary_union([shape(b["geometry"]) for e in events
                        for b in e["severity_bands"] if b["band"] == "moderate"])
    far = zone.buffer(FAR_DEG).difference(zone.buffer(NEAR_DEG))
    for _ in range(round(args.n * 0.4)):         # 40% unaffected
        i += 1
        buildings.append(make_building(rng, i, sample_point(rng, far)))

    out = ROOT / "data" / "buildings"
    out.mkdir(parents=True, exist_ok=True)
    (out / "buildings.json").write_text(json.dumps(buildings, indent=2), encoding="utf-8")
    cols = [k for k in buildings[0] if k != "sub_limits"] + ["contents_limit", "rebuild_modifier_cap"]
    with open(out / "buildings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for b in buildings:
            row = {k: v for k, v in b.items() if k != "sub_limits"}
            row["contents_limit"] = b["sub_limits"]["contents"]
            row["rebuild_modifier_cap"] = b["sub_limits"]["rebuild_modifier_cap"]
            w.writerow(row)
    print(f"Wrote {len(buildings)} buildings to {out}")


if __name__ == "__main__":
    main()