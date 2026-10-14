import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.vision import gemini  # noqa: E402

print("project:", os.getenv("GCP_PROJECT"), "| model:", os.getenv("GEMINI_MODEL"),
      "| location:", os.getenv("GEMINI_LOCATION") or os.getenv("GCP_REGION"))
client = gemini._client()
resp = client.models.generate_content(model=os.environ["GEMINI_MODEL"], contents="Reply with OK")
print("response:", resp.text)