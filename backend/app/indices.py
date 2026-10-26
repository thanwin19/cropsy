"""
indices.py — Index Results: per-parcel satellite index time series for a chosen date window.

Reads the real Sentinel-2 (NDVI, EVI, SAVI, NDRE, NDMI, NDWI) and Sentinel-1 (RVI, RSM) per-parcel observations built offline
by scripts/build_satellite.py and scripts/build_layers.py.  For each index it returns the series, the village median on the
same dates, and a comparison with the previous window of equal length.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import date, timedelta

from app import config

SAT_DIR = config.DATA_DIR / "satellite"

CATALOG = {
    "ndvi": dict(name="NDVI", unit="index", sensor="Sentinel-2", formula="(NIR - Red) / (NIR + Red)",
                 meaning="Greenness and vigour. Falls before a crop looks stressed to the eye."),
    "evi": dict(name="EVI", unit="index", sensor="Sentinel-2", formula="2.5 (NIR - Red) / (NIR + 6 Red - 7.5 Blue + 1)",
                meaning="Greenness that keeps responding in dense canopy where NDVI flattens."),
    "savi": dict(name="SAVI", unit="index", sensor="Sentinel-2", formula="1.5 (NIR - Red) / (NIR + Red + 0.5)",
                 meaning="Greenness corrected for bare soil showing through young or thin crops."),
    "ndre": dict(name="NDRE", unit="index", sensor="Sentinel-2", formula="(NIR - RedEdge1) / (NIR + RedEdge1)",
                 meaning="Chlorophyll / nitrogen status in a dense canopy."),
    "ndmi": dict(name="NDMI", unit="index", sensor="Sentinel-2", formula="(NIR - SWIR1) / (NIR + SWIR1)",
                 meaning="Water held inside the leaves; often drops before NDVI in drought."),
    "ndwi": dict(name="NDWI", unit="index", sensor="Sentinel-2", formula="(Green - NIR) / (Green + NIR)",
                 meaning="Open water and flooded surface. Positive over standing water."),
    "rvi": dict(name="Radar crop health (RVI)", unit="index 0..1", sensor="Sentinel-1", formula="4 VH / (VV + VH)",
                meaning="Canopy structure and biomass from radar; works through cloud."),
    "rsm": dict(name="Radar soil moisture (RSM)", unit="relative 0..1", sensor="Sentinel-1", formula="(dB - dry) / (wet - dry), per pixel",
                meaning="Relative surface wetness against the pixel's own driest and wettest day. Not volumetric."),
}
OPTICAL = ["ndvi", "evi", "savi", "ndre", "ndmi", "ndwi"]
RADAR = ["rvi", "rsm"]

_cache: dict = {}


def _load() -> dict:
    if _cache:
        return _cache
    series: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))   # index -> parcel -> [(date, value)]
    by_date: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))   # index -> date -> [values] (village)
    sectors: dict[str, dict[str, dict]] = defaultdict(dict)                        # parcel -> date -> {N: v, ...}
    f = SAT_DIR / "ndvi_observations.csv"
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8")):
            for k in OPTICAL:
                v = r.get(f"{k}_mean")
                if v not in (None, ""):
                    series[k][r["parcel_id"]].append((r["date"], float(v)))
                    by_date[k][r["date"]].append(float(v))
            sectors[r["parcel_id"]][r["date"]] = {c: float(r[f"ndvi_{c}"]) for c in ("N", "NE", "E", "SE", "S", "SW", "W", "NW") if r.get(f"ndvi_{c}")}
    f = SAT_DIR / "radar_observations.csv"
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8")):
            for k in RADAR:
                v = r.get(f"{k}_mean")
                if v not in (None, ""):
                    series[k][r["parcel_id"]].append((r["date"], float(v)))
                    by_date[k][r["date"]].append(float(v))
    for k in series:
        for p in series[k]:
            series[k][p].sort()
    med = {k: {d: round(statistics.median(v), 4) for d, v in dd.items()} for k, dd in by_date.items()}
    _cache.update(series=series, village_median=med, sectors=sectors)
    return _cache


def calendar() -> dict:
    f = SAT_DIR / "pass_calendar.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"sentinel2": [], "sentinel1": []}


def results(parcel_id: str, start: str | None = None, end: str | None = None, indices: list[str] | None = None) -> dict:
    d = _load()
    end_d = date.fromisoformat(end) if end else date.today()
    start_d = date.fromisoformat(start) if start else end_d - timedelta(days=365)
    span = (end_d - start_d).days + 1
    prev_end = start_d - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    out = {}
    for k in indices or list(CATALOG):
        pts = d["series"].get(k, {}).get(parcel_id, [])
        cur = [(t, v) for t, v in pts if start_d.isoformat() <= t <= end_d.isoformat()]
        prev = [v for t, v in pts if prev_start.isoformat() <= t <= prev_end.isoformat()]
        cm = statistics.mean(v for _, v in cur) if cur else None
        pm = statistics.mean(prev) if prev else None
        out[k] = {**CATALOG[k], "points": [{"date": t, "value": v, "village_median": d["village_median"].get(k, {}).get(t)} for t, v in cur],
                  "latest": ({"date": cur[-1][0], "value": cur[-1][1]} if cur else None),
                  "window_mean": round(cm, 4) if cm is not None else None, "previous_mean": round(pm, 4) if pm is not None else None,
                  "change_vs_previous": round(cm - pm, 4) if cm is not None and pm is not None else None,
                  "n_points": len(cur), "n_previous": len(prev)}
    return {"parcel_id": parcel_id, "start": start_d.isoformat(), "end": end_d.isoformat(),
            "previous_window": [prev_start.isoformat(), prev_end.isoformat()], "indices": out,
            "data_source": "real Sentinel-2 / Sentinel-1 at the parcel's coordinates; the crop labels are dummy"}


def field_directions(parcel_id: str) -> dict | None:
    """Which compass side of the parcel is weakest on the latest clear pass: where to inspect first."""
    d = _load()
    s = d["sectors"].get(parcel_id) or {}
    for t in sorted(s, reverse=True):
        sec = s[t]
        if len(sec) >= 4:
            order = sorted(sec.items(), key=lambda kv: kv[1])
            mean = statistics.mean(sec.values())
            return {"date": t, "sectors": sec, "weakest": order[0][0], "strongest": order[-1][0], "mean_ndvi": round(mean, 3),
                    "spread": round(order[-1][1] - order[0][1], 3),
                    "note": ("The sides differ little, so there is no clear place to start." if order[-1][1] - order[0][1] < 0.08 else
                             f"Start the walk on the {order[0][0]} side: its NDVI is {mean - order[0][1]:.2f} below the field average."),
                    "basis": "Mean NDVI of 8 compass sectors of the parcel on the latest clear Sentinel-2 pass (north is up)."}
    return None
