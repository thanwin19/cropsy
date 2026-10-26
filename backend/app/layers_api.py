"""
layers_api.py — Coordinate lookup over the map layers (value of every layer at a lat/lon) and parcel containment.
Reads the 8-bit layer PNGs built by scripts/build_layers.py (value = lo + (q-1)/254*(hi-lo), q = 0 means no data).
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
from PIL import Image

from app import config

LAYERS_DIR = config.DATA_DIR / "layers"


@lru_cache(maxsize=1)
def manifest() -> dict:
    return json.loads((LAYERS_DIR / "layers.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=64)
def _png(layer: str, month: str) -> np.ndarray:
    return np.array(Image.open(LAYERS_DIR / layer / f"{month}.png"))


@lru_cache(maxsize=1)
def _parcels() -> list[tuple[str, list]]:
    gj = json.loads((config.DATA_DIR / "village_parcels.geojson").read_text(encoding="utf-8"))
    return [(f["id"], f["geometry"]["coordinates"][0]) for f in gj["features"]]


def _inside(lon: float, lat: float, ring: list) -> bool:
    ok = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            ok = not ok
    return ok


def parcel_at(lat: float, lon: float) -> str | None:
    return next((pid for pid, ring in _parcels() if _inside(lon, lat, ring)), None)


def lookup(lat: float, lon: float) -> dict:
    m = manifest()
    (s, w), (n, e) = m["bounds"]
    if not (s <= lat <= n and w <= lon <= e):
        return {"inside": False, "lat": lat, "lon": lon, "note": "Outside the mapped Then Malai window.", "values": {}}
    W, H = m["size"]
    x = min(W - 1, int((lon - w) / (e - w) * W))
    y = min(H - 1, int((n - lat) / (n - s) * H))
    out: dict = {}
    for k, info in m["layers"].items():
        months = info["months"]
        if not months or k in ("hybrid", "colorblind", "etci"):
            continue
        month = "static" if months[0] == "static" else months[-1]
        try:
            px = _png(k, month)[y, x]
        except Exception:
            continue
        if k == "tci":
            out[k] = {"name": info["name"], "month": month, "rgb": [int(v) for v in px[:3]]}
            continue
        if px[-1] == 0:
            out[k] = {"name": info["name"], "month": month, "value": None}
        elif k == "lulc":
            hexc = "#%02x%02x%02x" % tuple(int(v) for v in px[:3])
            out[k] = {"name": info["name"], "month": month, "value": next((c["name"] for c in m["lulc_classes"].values() if c["color"].lower() == hexc), "land cover")}
        else:
            lo, hi = info["range"]
            out[k] = {"name": info["name"], "month": month, "units": info["units"], "value": round(lo + (int(px[0]) - 1) / 254 * (hi - lo), 3)}
    return {"inside": True, "lat": lat, "lon": lon, "parcel_id": parcel_at(lat, lon), "values": out,
            "note": "Latest available month of each layer. Real satellite data; crop labels in this project are dummy."}
