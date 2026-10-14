"""Build data/fixtures/hazard_events.json: fire (cached/live/simulated) + simulated typhoon.

Usage:
  python scripts/build_events.py                       # cached snapshot if present, else simulated fire
  python scripts/build_events.py --fire-source live --bbox 95,5,106,21
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from services.common import flags  # noqa: E402
from services.hazard import firms_client  # noqa: E402
from services.hazard.polygon import build_fire_events  # noqa: E402
from services.hazard.typhoon import simulate_typhoon  # noqa: E402

load_dotenv(ROOT / ".env")

ap = argparse.ArgumentParser()
ap.add_argument("--fire-source", choices=["live", "cached", "simulated"])
ap.add_argument("--bbox", default="100.3,13.8,100.7,14.2", help="west,south,east,north")
ap.add_argument("--typhoon-scenario", default=None)
args = ap.parse_args()

src = args.fire_source or ("cached" if firms_client.CACHE_PATH.exists() else "simulated")
bbox = tuple(float(v) for v in args.bbox.split(","))
print(f"Fire source: {src}")

with flags.overrides({"hazard.fire.source": src}):
    hotspots, label = firms_client.get_hotspots(bbox)
events = build_fire_events(hotspots, label)
print(f"Fire events: {len(events)} from {len(hotspots)} hotspots")

if events and flags.is_on("hazard.typhoon.enabled"):
    c_lat = sum(h["lat"] for h in hotspots) / len(hotspots)
    c_lng = sum(h["lng"] for h in hotspots) / len(hotspots)
    scenario = args.typhoon_scenario or flags.get("hazard.simulator.scenario")
    events.append(simulate_typhoon(c_lat, c_lng, scenario))
    print(f"Added typhoon scenario: {scenario}")

out = ROOT / "data" / "fixtures" / "hazard_events.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(events, indent=2), encoding="utf-8")
print(f"Wrote {len(events)} events -> {out}")