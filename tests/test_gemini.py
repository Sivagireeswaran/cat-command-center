"""Try the real vision engine on a folder of images.

Usage: python scripts/test_gemini.py --dir data/images/test_set [--recorded-type masonry] [--no-forensics]
Folder needs views named front, left, right, rear, damage_closeup (.jpg/.png/.webp).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.vision import gemini  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--recorded-type", default="unknown")
ap.add_argument("--no-forensics", action="store_true")
args = ap.parse_args()

images = gemini.load_images(args.dir)
print("Views found:", [i["label"] for i in images])
analysis = gemini.analyze({"construction_type": args.recorded_type}, images)
print("\n== Building analysis ==")
print(json.dumps(analysis.model_dump(), indent=2))
if not args.no_forensics:
    print("\n== Visual forensics ==")
    print(json.dumps(gemini.forensics(images), indent=2))