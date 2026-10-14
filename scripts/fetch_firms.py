"""Fetch live FIRMS hotspots, save a cached snapshot, and write HazardEvents for inspection.

Example:
  python scripts\\fetch_firms.py --bbox 95,5,106,21 --days 1
bbox is west,south,east,north. Use a small area where the FIRMS web map shows active fires.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from services.hazard import firms_client  # noqa: E402
from services.hazard.polygon import build_fire_events  # noqa: E402

load_dotenv(ROOT / ".env")

p = argparse.ArgumentParser()
p.add_argument("--bbox", required=True, help="west,south,east,north")
p.add_argument("--days", type=int, default=1)
p.add_argument("--source", default="VIIRS_SNPP_NRT")
args = p.parse_args()

bbox = tuple(float(v) for v in args.bbox.split(","))
hotspots = firms_client.fetch_live(bbox, days=args.days, source=args.source)
print(f"Fetched {len(hotspots)} hotspots")
if not hotspots:
    sys.exit("No hotspots in this area/time. Try a larger box, more days, or a different region.")

meta = {"bbox": bbox, "days": args.days, "source": args.source,
        "fetched_at": datetime.now(timezone.utc).isoformat()}
firms_client.save_snapshot(hotspots, meta)
print(f"Saved snapshot to {firms_client.CACHE_PATH}")

events = build_fire_events(hotspots, source="firms_live")
out = ROOT / "data" / "fixtures" / "hazard_events.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(events, indent=2), encoding="utf-8")
print(f"Built {len(events)} fire events -> {out}")
for e in events:
    print(e["event_id"], "hotspots:", e["parameters"]["hotspot_count"], "max_frp:", e["parameters"]["max_frp"])