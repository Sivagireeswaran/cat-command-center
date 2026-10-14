"""Generate mock claims for exposed buildings, run the pipeline, rank, and write data/fixtures/claims.json.

Examples:
  python scripts/run_pipeline.py --compare
  python scripts/run_pipeline.py --flags "auth.check.duplicates=off"
  python scripts/run_pipeline.py --flags "dispatch.priority_mode=fifo"

Mock-only: test_label records which claims were made fraudulent, so you can measure detection.
Fraud scenarios only apply when vision.mode=mock.
"""
import argparse
import hashlib
import json
import random
import sys
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.authenticity.checks import parse_ts  # noqa: E402
from services.common import flags  # noqa: E402
from services.dispatch.ranker import rank  # noqa: E402
from services.orchestrator.pipeline import process_claim  # noqa: E402
from services.vision.mock import default_scenario  # noqa: E402

CLAIM_RATE = {"extreme": 0.9, "high": 0.7, "moderate": 0.4, "projected": 0.2}
FMT = "%Y-%m-%dT%H:%M:%SZ"


def make_capture(b, ev, arrival, fraud, rng, pool, idx):
    lat, lng = b["lat"], b["lng"]
    if fraud == "edited":
        lat += 0.11                                   # about 12 km away from the insured address
        captured = parse_ts(ev["detected_at"]) - timedelta(hours=36)
    else:
        lat += rng.gauss(0, 0.0001)
        lng += rng.gauss(0, 0.0001)
        captured = arrival - timedelta(seconds=20)
    if fraud == "duplicate" and pool:
        hashes = list(rng.choice(pool))
    else:
        hashes = [hashlib.sha256(f"{b['building_id']}:{k}".encode()).hexdigest()[:16] for k in range(5)]
    pool.append(hashes)
    return {"capture_session_id": f"cap_{idx:04d}",
            "gps": {"lat": lat, "lng": lng, "accuracy_m": 12.0},
            "captured_at_client": captured.strftime(FMT),
            "received_at_server": arrival.strftime(FMT),
            "image_hashes": hashes}


def build_claims(data, seed):
    events = {e["event_id"]: e for e in data["events"]}
    pending = []
    for b in data["buildings"]:
        band = b.get("band")
        if not band:
            continue
        rng = random.Random(f"{seed}:{b['building_id']}")
        if rng.random() > CLAIM_RATE[band]:
            continue
        ev = events[b["event_id"]]
        r = rng.random()
        fraud = "edited" if r < 0.06 else ("duplicate" if r < 0.10 else None)
        arrival = parse_ts(ev["detected_at"]) + timedelta(minutes=rng.uniform(10, 600))
        pending.append((arrival, b, ev, fraud, rng))
    pending.sort(key=lambda t: t[0])

    seen, pool, claims = {}, [], []
    for idx, (arrival, b, ev, fraud, rng) in enumerate(pending, start=1):
        scenario = "edited" if fraud == "edited" else default_scenario(b)
        capture = make_capture(b, ev, arrival, fraud, rng, pool, idx)
        c = process_claim(f"CLM-{50000 + idx}", b, ev, capture, seen,
                          arrival.strftime(FMT), scenario=scenario)
        c["test_label"] = fraud or "honest"
        claims.append(c)
    return claims


def report(claims):
    from collections import Counter
    print("Recommendations:", dict(Counter(c["recommendation"] for c in claims)))
    fraud = [c for c in claims if c["test_label"] != "honest"]
    honest = [c for c in claims if c["test_label"] == "honest"]
    caught = [c for c in fraud if c["recommendation"] == "manual_review"]
    wrongly = [c for c in honest if c["recommendation"] == "manual_review"]
    print(f"Fraud caught: {len(caught)}/{len(fraud)}   Honest claims flagged: {len(wrongly)}/{len(honest)}")
    print("\nTop 10 in queue:")
    print(f"{'rank':>4} {'claim':<10} {'band':<9} {'severity':>8} {'risk':>6}  {'recommendation':<14} label")
    for c in claims[:10]:
        risk = c["authenticity"]["manipulation_risk"]
        print(f"{c['priority_rank']:>4} {c['claim_id']:<10} {str(c['band']):<9} "
              f"{c['damage_summary']['overall_severity']:>8} {str(risk):>6}  "
              f"{c['recommendation']:<14} {c['test_label']}")


def compare(claims):
    top = sorted(claims, key=lambda c: -c["damage_summary"]["overall_severity"])[:10]
    ids = {c["claim_id"] for c in top}
    print("\nMean queue position of the 10 most-damaged claims (lower is better):")
    for mode in ("severity_exposure", "severity_only", "fifo"):
        with flags.overrides({"dispatch.priority_mode": mode}):
            ranked = rank([dict(c) for c in claims])
        pos = [c["priority_rank"] for c in ranked if c["claim_id"] in ids]
        print(f"  {mode:<18} {sum(pos) / len(pos):5.1f}  (of {len(ranked)} claims)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="5")
    ap.add_argument("--flags", default="", help='e.g. "auth.enabled=off,vision.damage=off"')
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()

    data = json.loads((ROOT / "data/fixtures/map_data.json").read_text(encoding="utf-8"))
    ctx = flags.overrides(flags.parse_override(args.flags)) if args.flags else nullcontext()
    with ctx:
        claims = rank(build_claims(data, args.seed))
        out = ROOT / "data/fixtures/claims.json"
        out.write_text(json.dumps(claims, indent=2), encoding="utf-8")
        print(f"Wrote {len(claims)} claims -> {out}   (priority_mode={flags.get('dispatch.priority_mode')},"
              f" auth.enabled={flags.get('auth.enabled')})")
        report(claims)
        if args.compare:
            compare(claims)


if __name__ == "__main__":
    main()