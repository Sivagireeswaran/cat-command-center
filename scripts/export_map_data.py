"""Join events + buildings + exposure into one file for the map: data/fixtures/map_data.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.common import flags  # noqa: E402
from services.exposure.query import find_exposed, summarize  # noqa: E402

RANK = {"extreme": 3, "high": 2, "moderate": 1, "projected": 0}

events = json.loads((ROOT / "data/fixtures/hazard_events.json").read_text(encoding="utf-8"))
buildings = json.loads((ROOT / "data/buildings/buildings.json").read_text(encoding="utf-8"))

status, summaries = {}, {}
with flags.overrides({"exposure.engine": "local"}):
    for e in events:
        exposed = find_exposed(e, buildings)
        summaries[e["event_id"]] = summarize(exposed)
        for b in exposed:
            cur = status.get(b["building_id"])
            if cur is None or RANK[b["severity_band"]] > RANK[cur["band"]]:
                status[b["building_id"]] = {"band": b["severity_band"], "event_id": e["event_id"]}

out_buildings = [{**b, "band": status.get(b["building_id"], {}).get("band"),
                  "event_id": status.get(b["building_id"], {}).get("event_id")} for b in buildings]
out = ROOT / "data/fixtures/map_data.json"
out.write_text(json.dumps({"events": events, "buildings": out_buildings, "summaries": summaries},
                          indent=2), encoding="utf-8")
print(f"Wrote {out}")
for eid, s in summaries.items():
    print(eid, s["total_buildings"], "buildings,", s["total_insured_value"], "insured value")