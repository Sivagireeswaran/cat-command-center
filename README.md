# CAT Command Center

AI-powered catastrophe triage for property insurance. Built for the Google Cloud AI Builder Cup 2026.

Hazard events (real NASA FIRMS fire data, simulated typhoon) -> insured buildings in the zone -> claim analysis
from guided photos (Gemini on Vertex AI) -> authenticity checks -> ranked adjuster queue on a map.

All buildings, policies and claims are synthetic. Hazard projections and simulated events are estimates.
The system recommends; a human decides. Nothing is auto-denied.

## Quick start (Windows, Python 3.10+)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests -q
python scripts\build_events.py
python scripts\gen_buildings.py --n 200
python scripts\export_map_data.py
python scripts\run_pipeline.py --compare
python -m http.server 8000
```
Open http://localhost:8000/web/command-center/index.html

## Feature flags
Every function sits behind a flag in `config/flags.default.json`. Override locally in
`config/flags.local.json` or per run, e.g. `python scripts\run_pipeline.py --flags "auth.enabled=off"`.
Defaults run fully offline (cached hazard data, mock vision).

## Real services
Copy `.env.example` to `.env` and fill in GCP_PROJECT, GEMINI_MODEL, FIRMS_MAP_KEY.
Set `vision.mode=gemini` to use real Gemini vision.