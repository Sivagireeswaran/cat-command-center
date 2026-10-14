"""Find insured buildings inside a HazardEvent (flag: exposure.engine = local | bigquery)."""
import os

from shapely.geometry import Point, shape

from services.common import flags

SEVERITY_ORDER = ["extreme", "high", "moderate"]


def _local(event: dict, buildings: list[dict]) -> list[dict]:
    bands = sorted(
        ((b["band"], shape(b["geometry"])) for b in event["severity_bands"]),
        key=lambda x: SEVERITY_ORDER.index(x[0]),
    )
    proj = shape(event["projection"]) if event.get("projection") else None
    out = []
    for b in buildings:
        pt = Point(b["lng"], b["lat"])
        band = next((name for name, geom in bands if geom.covers(pt)), None)
        in_proj = bool(proj and proj.covers(pt))
        if band or in_proj:
            out.append({**b, "event_id": event["event_id"],
                        "severity_band": band or "projected", "in_projection": in_proj})
    return out


def _bigquery(event: dict) -> list[dict]:
    """UNTESTED: expects table <project>.<dataset>.insured_buildings with lat and lng columns.
    Uses bands only (projection not applied here). If GeoJSON parsing fails, check the polygon
    ring orientation or that make_valid is supported in your BigQuery version.
    """
    import json

    from google.cloud import bigquery

    project, dataset = os.environ["GCP_PROJECT"], os.environ["BQ_DATASET"]
    bands = {b["band"]: json.dumps(b["geometry"]) for b in event["severity_bands"]}
    pt = "ST_GEOGPOINT(b.lng, b.lat)"

    def cov(name):
        return f"ST_COVERS(ST_GEOGFROMGEOJSON(@{name}, make_valid => TRUE), {pt})"

    sql = f"""
    SELECT b.*,
      CASE WHEN {cov('extreme')} THEN 'extreme'
           WHEN {cov('high')} THEN 'high'
           ELSE 'moderate' END AS severity_band
    FROM `{project}.{dataset}.insured_buildings` b
    WHERE {cov('moderate')}
    """
    params = [bigquery.ScalarQueryParameter(n, "STRING", g) for n, g in bands.items()]
    job = bigquery.Client(project=project).query(
        sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    return [{**dict(r), "event_id": event["event_id"], "in_projection": False} for r in job.result()]


def find_exposed(event: dict, buildings: list[dict] | None = None) -> list[dict]:
    engine = flags.get("exposure.engine")
    if engine == "local":
        if buildings is None:
            raise ValueError("local engine needs the buildings list")
        return _local(event, buildings)
    if engine == "bigquery":
        return _bigquery(event)
    raise ValueError(f"Unknown exposure.engine: {engine}")


def summarize(exposed: list[dict]) -> dict:
    out = {"total_buildings": len(exposed),
           "total_insured_value": sum(b["insured_value"] for b in exposed), "by_band": {}}
    for b in exposed:
        s = out["by_band"].setdefault(b["severity_band"], {"count": 0, "insured_value": 0})
        s["count"] += 1
        s["insured_value"] += b["insured_value"]
    return out