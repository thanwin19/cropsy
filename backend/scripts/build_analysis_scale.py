"""Analysis scale per parcel: the share of each parcel's pixels in five health classes, from the latest NDVI and NDMI composites.

Rule-of-thumb classes (NOT agronomically calibrated; they exist to show WHERE inside a field and HOW MUCH of it looks weak):
  bare_or_no_crop        NDVI < 0.20
  good                   NDVI >= 0.50 and NDMI >= 0.10
  irrigation_attention   NDVI >= 0.35 and NDMI < 0.10      (green cover but low canopy water)
  critical               0.20 <= NDVI < 0.35 and NDMI < 0.10 (weak cover and dry canopy)
  crop_attention         everything else                     (moderate vigour with adequate water)
Run: python backend/scripts/build_analysis_scale.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.features import geometry_mask

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_layers as bl  # noqa: E402
import build_satellite as bs  # noqa: E402

LAYERS = bs.DATA / "layers"


def load(layer, month):
    im = np.array(Image.open(LAYERS / layer / f"{month}.png"))
    lo, hi = json.loads((LAYERS / "layers.json").read_text())["layers"][layer]["range"]
    v = lo + (im[..., 0].astype("float32") - 1) / 254 * (hi - lo)
    v[im[..., 1] == 0] = np.nan
    return v


def main():
    parcels = bs.load_parcels()
    bl.setup_grid(bs.bbox_of(parcels))
    man = json.loads((LAYERS / "layers.json").read_text())
    month = sorted(set(man["months"]["ndvi"]) & set(man["months"]["ndmi"]))[-1]
    ndvi, ndmi = load("ndvi", month), load("ndmi", month)
    cls = np.full(ndvi.shape, -1, dtype=int)                      # -1 = no data (cloud / masked)
    ok = np.isfinite(ndvi) & np.isfinite(ndmi)
    cls[ok] = 4                                                     # crop_attention by default
    cls[ok & (ndvi < 0.35) & (ndmi < 0.10)] = 3                     # critical
    cls[ok & (ndvi >= 0.35) & (ndmi < 0.10)] = 2                    # irrigation_attention
    cls[ok & (ndvi >= 0.50) & (ndmi >= 0.10)] = 0                   # good
    cls[ok & (ndvi < 0.20)] = 1                                     # bare or no crop
    names = ["good", "bare_or_no_crop", "irrigation_attention", "critical", "crop_attention"]
    out = {}
    for pid, geom in parcels:
        m = geometry_mask([geom], out_shape=cls.shape, transform=bl.TRANSFORM, invert=True)
        n = int(m.sum())
        if not n:
            continue
        c = cls[m]
        valid = c >= 0
        entry = {nm: round(float((c == i).sum()) / max(valid.sum(), 1), 3) for i, nm in enumerate(names)}
        entry["clear_fraction"] = round(float(valid.mean()), 2)
        out[pid] = entry
    (bs.DATA / "satellite" / "analysis_scale.json").write_text(json.dumps({
        "month": month, "rules": __doc__.split("Rule-of-thumb")[1].split("Run:")[0].strip(), "parcels": out,
        "note": "Rule-of-thumb health classes from real Sentinel-2 NDVI and NDMI; not agronomically calibrated."}, indent=1), encoding="utf-8")
    tot = {nm: round(float(np.mean([e[nm] for e in out.values()])), 3) for nm in names}
    print(f"{len(out)} parcels, month {month}, village-average class shares: {tot}")


if __name__ == "__main__":
    main()
