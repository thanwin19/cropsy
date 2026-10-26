"""field_analysis.py: satellite evidence for ONE parcel, with provenance, and pixel-level zones inside the field.

Where the numbers come from (nothing here is invented; every value keeps its basis and date):
  latest scene   data/satellite/ndvi_observations.csv, written by scripts/build_satellite.py: one Sentinel-2 L2A scene, cloud-masked with the scene
                 classification layer, MEAN over the valid 10 m pixels inside the parcel boundary (plus 8 compass-sector means of NDVI).
  baseline       mean NDVI of the scenes 15 to 75 days before the latest one (data/satellite/ndvi_summary.json).
  monthly layer  data/layers/<layer>/<YYYY-MM>.png, written by scripts/build_layers.py: a cloud-masked MONTHLY MEDIAN composite on a 0.0001 degree
                 (about 11 m) grid. The map-lookup API reads ONE pixel at the parcel centre; this module reads every pixel inside the boundary.
So "0.2653 on 29 Sep" (one scene, parcel mean) and "0.239 for September" (monthly composite, centre pixel) were never the same quantity. They are reported separately.

Zones: the parcel's pixels are cut into a 3 x 3 grid of cells; a cell needs at least MIN_CELL_PX valid pixels. A cell is 'lower' / 'higher' than the rest of the
field only when it differs from the parcel mean by at least max(0.05, 0.75 x the parcel's pixel standard deviation). These thresholds are documented
choices, not agronomic constants. A lower cell is a place to walk and look, not a diagnosis."""
from __future__ import annotations

import csv
import json
from datetime import date
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from app import config

LAYERS_DIR = config.DATA_DIR / "layers"
GRID = 3
MIN_CELL_PX = 6
MIN_PARCEL_PX = 36
STALE_DAYS = 45
SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


@lru_cache(maxsize=1)
def _manifest() -> dict:
    return json.loads((LAYERS_DIR / "layers.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _rings() -> dict[str, list]:
    gj = json.loads((config.DATA_DIR / "village_parcels.geojson").read_text(encoding="utf-8"))
    return {f["id"]: f["geometry"]["coordinates"][0] for f in gj["features"]}


@lru_cache(maxsize=64)
def _png(layer: str, month: str) -> np.ndarray:
    return np.array(Image.open(LAYERS_DIR / layer / f"{month}.png"))


@lru_cache(maxsize=1)
def _observations() -> dict[str, list[dict]]:
    f = config.DATA_DIR / "satellite" / "ndvi_observations.csv"
    out: dict[str, list[dict]] = {}
    if f.exists():
        with open(f, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                out.setdefault(r["parcel_id"], []).append(r)
    for rows in out.values():
        rows.sort(key=lambda r: r["date"])
    return out


@lru_cache(maxsize=1)
def _summary() -> dict:
    f = config.DATA_DIR / "satellite" / "ndvi_summary.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _num(v):
    try:
        return round(float(v), 4) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def _grid_geometry():
    m = _manifest()
    (s, w), (n, e) = m["bounds"]
    W, H = m["size"]
    return m, s, w, n, e, W, H


def _parcel_mask(pid: str):
    """Boolean mask of the pixels whose centre is inside the parcel, cropped to its bounding box. Returns (mask, x0, y0) or None."""
    ring = _rings().get(pid)
    if not ring:
        return None
    m, s, w, n, e, W, H = _grid_geometry()
    pts = [((lon - w) / (e - w) * W, (n - lat) / (n - s) * H) for lon, lat in ring]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = int(max(0, min(xs))), int(min(W, max(xs)) + 1), int(max(0, min(ys))), int(min(H, max(ys)) + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    img = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(img).polygon([(x - x0 - 0.5, y - y0 - 0.5) for x, y in pts], fill=1)     # pixel (i, j) is centred at (i, j)
    return np.array(img, dtype=bool), x0, y0


def _values(layer: str, month: str):
    m = _manifest()
    info = m["layers"][layer]
    lo, hi = info["range"]
    a = _png(layer, month)
    q = a[..., 0].astype(np.float32)
    valid = a[..., -1] > 0
    valid &= q > 0
    return lo + (q - 1) / 254 * (hi - lo), valid


def latest_month(layer: str) -> str | None:
    months = _manifest()["layers"].get(layer, {}).get("months") or []
    return months[-1] if months else None


def parcel_layer_mean(pid: str, layer: str, month: str | None = None) -> dict | None:
    """Mean of a monthly layer over the valid pixels inside the parcel. None if the layer, month or parcel is unavailable."""
    month = month or latest_month(layer)
    pm = _parcel_mask(pid)
    if not month or pm is None:
        return None
    try:
        vals, valid = _values(layer, month)
    except Exception:  # noqa: BLE001
        return None
    mask, x0, y0 = pm
    h, w = mask.shape
    sub, ok = vals[y0:y0 + h, x0:x0 + w], valid[y0:y0 + h, x0:x0 + w]
    h2, w2 = sub.shape
    inside = mask[:h2, :w2]
    use = inside & ok
    if int(use.sum()) == 0:
        return {"layer": layer, "month": month, "mean": None, "n_valid": 0, "n_inside": int(inside.sum())}
    v = sub[use]
    return {"layer": layer, "month": month, "mean": round(float(v.mean()), 3), "median": round(float(np.median(v)), 3), "std": round(float(v.std()), 3),
            "n_valid": int(use.sum()), "n_inside": int(inside.sum()), "valid_frac": round(float(use.sum()) / max(1, int(inside.sum())), 2)}


def zones(pid: str, layer: str = "ndvi", month: str | None = None) -> dict:
    """Real pixel-level zones inside the parcel from the monthly raster. Never simulated: if the data cannot support it, says why."""
    month = month or latest_month(layer)
    base = {"parcel_id": pid, "layer": layer, "month": month, "available": False}
    info = _manifest()["layers"].get(layer)
    if not info or not month:
        return {**base, "reason": f"no monthly raster for layer '{layer}'"}
    pm = _parcel_mask(pid)
    if pm is None:
        return {**base, "reason": "unknown parcel or its boundary lies outside the mapped window"}
    mask, x0, y0 = pm
    try:
        vals, valid = _values(layer, month)
    except Exception:  # noqa: BLE001
        return {**base, "reason": f"no {layer} raster for {month} (months on file: {', '.join(info.get('months') or []) or 'none'})"}
    h, w = mask.shape
    sub, ok = vals[y0:y0 + h, x0:x0 + w], valid[y0:y0 + h, x0:x0 + w]
    h2, w2 = sub.shape
    inside = mask[:h2, :w2]
    use = inside & ok
    n_in, n_ok = int(inside.sum()), int(use.sum())
    prov = {"source": info.get("source"), "kind": info.get("kind"), "resolution": f"{_manifest()['resolution_deg']} degree grid (about 11 m)",
            "basis": "monthly cloud-masked median composite, every pixel inside the parcel boundary", "month": month}
    if n_ok < MIN_PARCEL_PX:
        return {**base, "provenance": prov, "n_inside": n_in, "n_valid": n_ok,
                "reason": f"only {n_ok} clear pixels inside this parcel ({n_in} in total); at about 11 m a parcel needs at least {MIN_PARCEL_PX} to show differences inside it"}
    v = sub[use]
    pmean, pstd = float(v.mean()), float(v.std())
    thr = max(0.05, 0.75 * pstd)
    m_, s_, w_, n_, e_, W, H = _grid_geometry()
    ys_, xs_ = np.nonzero(inside)
    cy0, cy1, cx0, cx1 = ys_.min(), ys_.max() + 1, xs_.min(), xs_.max() + 1
    cells = []
    for gy in range(GRID):
        for gx in range(GRID):
            ya, yb = cy0 + (cy1 - cy0) * gy // GRID, cy0 + (cy1 - cy0) * (gy + 1) // GRID
            xa, xb = cx0 + (cx1 - cx0) * gx // GRID, cx0 + (cx1 - cx0) * (gx + 1) // GRID
            sel = np.zeros_like(use)
            sel[ya:yb, xa:xb] = True
            cell_ok = use & sel
            k = int(cell_ok.sum())
            ring = [[w_ + (e_ - w_) * (x0 + xa) / W, n_ - (n_ - s_) * (y0 + ya) / H], [w_ + (e_ - w_) * (x0 + xb) / W, n_ - (n_ - s_) * (y0 + ya) / H],
                    [w_ + (e_ - w_) * (x0 + xb) / W, n_ - (n_ - s_) * (y0 + yb) / H], [w_ + (e_ - w_) * (x0 + xa) / W, n_ - (n_ - s_) * (y0 + yb) / H]]
            name = (["north", "centre", "south"][gy] if gx == 1 and gy != 1 else ["north-west", "west", "south-west"][gy] if gx == 0 and gy != 1 else
                    ["north-east", "east", "south-east"][gy] if gx == 2 and gy != 1 else "centre-west" if gx == 0 else "centre-east" if gx == 2 else "centre")
            if k < MIN_CELL_PX:
                cells.append({"name": name, "class": "no_data", "n_valid": k, "ring": ring, "mean": None})
                continue
            cm = float(sub[cell_ok].mean())
            cls = "lower" if cm <= pmean - thr else "higher" if cm >= pmean + thr else "typical"
            cells.append({"name": name, "class": cls, "n_valid": k, "mean": round(cm, 3), "vs_parcel": round(cm - pmean, 3), "ring": ring})
    return {**base, "available": True, "provenance": prov, "n_inside": n_in, "n_valid": n_ok, "valid_frac": round(n_ok / max(1, n_in), 2),
            "parcel_mean": round(pmean, 3), "parcel_std": round(pstd, 3), "threshold": round(thr, 3), "cells": cells,
            "method": f"{GRID}x{GRID} grid of the parcel's pixels; a cell is 'lower' or 'higher' when its mean differs from the parcel mean by at least {round(thr, 3)} (the larger of 0.05 and 0.75 x the pixel standard deviation); a cell needs {MIN_CELL_PX}+ clear pixels",
            "caution": "A lower zone is a place to inspect on foot. Shade, a wet patch, a gap in planting, a path or a different crop stage can all lower it; it is not a diagnosis."}


def canonical(pid: str) -> dict | None:
    """One structure with every satellite value for the parcel, each with its basis and date, plus the reason the values differ."""
    rows = _observations().get(pid) or []
    summ = ((_summary().get("parcels") or {}).get(pid)) or {}
    as_of = _summary().get("as_of")
    if not rows and not summ:
        return None
    out: dict = {"parcel_id": pid, "as_of": as_of, "source": _summary().get("source")}
    if rows:
        r = rows[-1]
        age = None
        try:
            age = (date.fromisoformat(as_of) - date.fromisoformat(r["date"])).days if as_of else None
        except ValueError:
            pass
        out["latest_scene"] = {"date": r["date"], "age_days": age, "stale": (age is not None and age > STALE_DAYS), "scene_cloud_pct": _num(r.get("scene_cloud_pct")),
                               "valid_fraction": _num(r.get("valid_frac")), "n_pixels": int(r["n_pixels"]) if r.get("n_pixels") else None,
                               "basis": "one Sentinel-2 L2A scene, cloud-masked, mean over the valid pixels inside the parcel boundary",
                               "indices": {k: _num(r.get(f"{k}_mean")) for k in ("ndvi", "evi", "savi", "ndre", "ndmi", "ndwi")},
                               "ndvi_pixel_std": _num(r.get("ndvi_std")),
                               "sectors": {s: _num(r.get(f"ndvi_{s}")) for s in SECTORS}}
    if summ:
        if summ.get("baseline_ndvi") is not None:
            out["baseline"] = {"ndvi": summ.get("baseline_ndvi"), "n_scenes": summ.get("n_baseline"), "basis": "mean parcel NDVI of the scenes 15 to 75 days before the latest scene"}
        out["change_vs_baseline"] = summ.get("change")
        out["status"] = summ.get("status")
        out["status_rule"] = "stress: change <= -0.10; watch: <= -0.05; otherwise normal; 'insufficient' if fewer than 2 baseline scenes or the latest scene is older than 45 days"
        if summ.get("reason"):
            out["status_reason"] = summ["reason"]
    mon = parcel_layer_mean(pid, "ndvi")
    if mon:
        out["monthly_composite"] = {**mon, "basis": "monthly cloud-masked median composite, mean over the pixels inside the parcel boundary"}
    out["why_values_differ"] = ("The latest-scene value is one satellite pass on one day; the monthly value is a median of that month's clear passes, so the two are different "
                                "quantities and will not match. The map's point lookup reads a single pixel at the parcel centre, which also differs from a parcel mean.")
    return out


def evidence_text(pid: str, with_zones: bool = False) -> str:
    """Plain text for the answer prompt. Every line states what the number is and its date."""
    c = canonical(pid)
    if not c:
        return f"SATELLITE: no satellite summary is available for {pid}. Say so; do not guess values."
    L = [f"SATELLITE EVIDENCE for {pid} (real Sentinel-2 data; crop labels are dummy). Use only these numbers:"]
    ls = c.get("latest_scene")
    if ls:
        ix = ", ".join(f"{k.upper()} {v}" for k, v in ls["indices"].items() if v is not None)
        L.append(f"- Latest scene {ls['date']} ({ls['age_days']} days before {c.get('as_of')}{', STALE' if ls['stale'] else ''}): parcel mean {ix}; valid pixels {ls['valid_fraction']}; basis: {ls['basis']}.")
    if c.get("baseline"):
        b = c["baseline"]
        L.append(f"- Baseline NDVI {b['ndvi']} ({b['n_scenes']} scenes, {b['basis']}); change vs baseline {c.get('change_vs_baseline')}; status {c.get('status')}"
                 + (f" ({c['status_reason']})" if c.get("status_reason") else "") + f". Rule: {c['status_rule']}.")
    else:
        L.append("- No historical baseline is available" + (f" ({c['status_reason']})" if c.get("status_reason") else "") + f", status {c.get('status')}: do not compare with the past and do not say the vegetation is rising or falling.")
    mc = c.get("monthly_composite")
    if mc and mc.get("mean") is not None:
        L.append(f"- Monthly composite {mc['month']}: NDVI parcel mean {mc['mean']} ({mc['n_valid']} clear pixels of {mc['n_inside']}); basis: {mc['basis']}.")
    L.append("- " + c["why_values_differ"])
    if with_zones:
        z = zones(pid)
        if not z["available"]:
            L.append(f"- Spatial detail inside the field: NOT available ({z['reason']}). Say this plainly; do not name a corner.")
        else:
            lows = [x for x in z["cells"] if x["class"] == "lower"]
            L.append(f"- Spatial zones inside the field ({z['provenance']['month']} composite, {z['method']}): parcel mean {z['parcel_mean']}.")
            if lows:
                L.append("  Lower-than-rest zones: " + "; ".join(f"{x['name']} (mean {x['mean']}, {x['vs_parcel']} vs parcel, {x['n_valid']} pixels)" for x in lows) + ".")
            else:
                L.append("  No zone differs from the rest of the field by more than the threshold: the field looks even at this resolution.")
            L.append(f"  Caution: {z['caution']}")
    return "\n".join(L)
