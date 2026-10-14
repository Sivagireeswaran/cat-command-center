"""Report which .env values are set (never prints the values)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

NEEDED_NOW = ["GCP_PROJECT", "GCP_REGION", "GEMINI_MODEL"]
OPTIONAL = ["FIRMS_MAP_KEY", "BQ_DATASET", "GCS_BUCKET", "PUBSUB_HAZARD_TOPIC",
            "PUBSUB_FNOL_TOPIC", "DATABASE_URL"]

for group, keys in (("Needed now", NEEDED_NOW), ("Later", OPTIONAL)):
    print(group)
    for k in keys:
        print(f"  {k:<22} {'set' if os.getenv(k) else 'MISSING'}")