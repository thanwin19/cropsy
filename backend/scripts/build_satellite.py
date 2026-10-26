"""Compute REAL Sentinel-2 NDVI for every Then Malai parcel (offline, free, no account or key).

Source : Sentinel-2 L2A cloud-optimised GeoTIFFs on AWS Open Data, found through the open Earth Search STAC API.
Method : for each scene, read red (B04), NIR (B08) and the scene-classification layer (SCL) for the village window,
         mask cloud / shadow / cirrus / snow / defective pixels, and average NDVI inside each parcel polygon.
Output : backend/data/satellite/ndvi_observations.csv   one row per parcel per usable scene
         backend/data/satellite/ndvi_summary.json        per-parcel latest NDVI, baseline, change, status
Notes  : the satellite sees what is really growing at the parcel's real coordinates. The crop names, stages and issues
         in this project are dummy, so every output is labelled "real satellite data, dummy crop labels".
Run    : python backend/scripts/build_satellite.py [--days 365] [--as-of 2026-10-03]
"""
import argparse
import csv
import json
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.warp import transform_bounds, transform_geom
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend" / "data"
OUT = DATA / "satellite"
STAC = "https://earth-search.aws.element84.com/v1"
BAD_SCL = {0, 1, 3, 8, 9, 10, 11}   # no data, defective, cloud shadow, cloud (medium/high), thin cirrus, snow/ice
MIN_VALID_FRAC = 0.5
MIN_PIXELS = 8
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="1", GDAL_HTTP_TIMEOUT="30", VSI_CACHE="TRUE")


def load_parcels():
    gj = json.loads((DATA / "village_parcels.geojson").read_text(encoding="utf-8"))
    return [(f["id"], f["geometry"]) for f in gj["features"]]


def bbox_of(parcels, pad=0.001):
    xs = [c[0] for _, g in parcels for c in g["coordinates"][0]]
    ys = [c[1] for _, g in parcels for c in g["coordinates"][0]]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def scene_offset(red_dn: np.ndarray) -> float:
    """The reflectance offset actually present in this scene's pixel values (0.0 or -0.1), found from the data itself.

    ESA adds +1000 to the DN of newer scenes, so with that offset present reflectance >= 0 means DN >= ~1000 and almost no
    pixel can fall below it. Earth Search's metadata (raster:bands offset, earthsearch:boa_offset_applied) turned out NOT to
    be reliable: scenes flagged either way held offset-free values. Dark vegetation and water pixels give a direct answer:
    if the 5th percentile of the red band is below DN 900, the offset is not in the data (offset 0)."""
    v = red_dn[red_dn > 0]
    if v.size == 0:
        return -0.1
    return 0.0 if float(np.percentile(v, 5)) < 900 else -0.1


def _reflectance(arr, asset, offset=None):
    """DN -> surface reflectance = DN * scale + offset, where `offset` comes from scene_offset() (never from the metadata)."""
    rb = (asset.extra_fields.get("raster:bands") or [{}])[0]
    scale = rb.get("scale", 1e-4)
    if offset is None:
        offset = rb.get("offset", -0.1)
    return arr.astype("float32") * scale + offset


INDEX_FIELDS = ["ndvi", "evi", "savi", "ndre", "ndmi", "ndwi"]
SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]   # compass sectors around the parcel centre (north is up)
MIN_SECTOR_PIXELS = 5


def _read_band(item, name, b, shape, ref_win=None, ref_ds=None):
    """Read one band for the village window, resampled to the 10 m grid of `shape`."""
    with rasterio.open(item.assets[name].href) as ds:
        if ref_win is not None and ds.transform == ref_ds.transform and ds.shape == ref_ds.shape:
            return ds.read(1, window=ref_win)            # same 10 m grid as red
        w = from_bounds(*b, transform=ds.transform).round_offsets().round_lengths()
        return ds.read(1, window=w, out_shape=shape, resampling=Resampling.bilinear)


def process_scene(item, parcels, bbox):
    """Return a list of observation dicts for one scene (empty if unusable).

    Indices (reflectance = DN*scale+offset):
      NDVI = (NIR-Red)/(NIR+Red)                           greenness / vigour
      EVI  = 2.5*(NIR-Red)/(NIR+6*Red-7.5*Blue+1)           greenness that does not saturate in dense canopy
      SAVI = 1.5*(NIR-Red)/(NIR+Red+0.5)                    greenness corrected for bare soil (young crops)
      NDRE = (NIR-RedEdge1)/(NIR+RedEdge1)                  chlorophyll / nitrogen status in dense canopy
      NDMI = (NIR-SWIR1)/(NIR+SWIR1)                        canopy water content
      NDWI = (Green-NIR)/(Green+NIR)                        open water / very wet surface (McFeeters)
    Also the mean NDVI of each of 8 compass sectors of the parcel ("field directions": which side to inspect first).
    """
    rows = []
    try:
        with rasterio.Env(**GDAL_ENV):
            with rasterio.open(item.assets["red"].href) as red_ds:
                crs = red_ds.crs
                b = transform_bounds("EPSG:4326", crs, *bbox)
                win = from_bounds(*b, transform=red_ds.transform).round_offsets().round_lengths()
                red = red_ds.read(1, window=win)
                tr = red_ds.window_transform(win)
                shape = red.shape
                nir = _read_band(item, "nir", b, shape, win, red_ds)
                blue = _read_band(item, "blue", b, shape, win, red_ds)
                green = _read_band(item, "green", b, shape, win, red_ds)
                re1 = _read_band(item, "rededge1", b, shape)
                sw1 = _read_band(item, "swir16", b, shape)
            with rasterio.open(item.assets["scl"].href) as ds:
                swin = from_bounds(*b, transform=ds.transform).round_offsets().round_lengths()
                scl = ds.read(1, window=swin, out_shape=shape, resampling=Resampling.nearest)
    except Exception as e:  # network or format problem: skip the scene, report it
        print(f"  skip {item.id}: {type(e).__name__}: {str(e)[:90]}", file=sys.stderr)
        return rows

    off = scene_offset(red)
    # Reflectance = DN*scale + offset. Dense green canopy is very dark in red and blue, so after the -0.1 offset it sits at or
    # just below 0. Those are the HEALTHIEST pixels: floor them at 0 instead of discarding them (discarding biases NDVI low).
    floor = lambda a: np.maximum(a, 0.0)
    r = floor(_reflectance(red, item.assets["red"], off))
    n = floor(_reflectance(nir, item.assets["nir"], off))
    bl = floor(_reflectance(blue, item.assets["blue"], off))
    e1 = floor(_reflectance(re1, item.assets["rededge1"], off))
    s1 = floor(_reflectance(sw1, item.assets["swir16"], off))
    gr = floor(_reflectance(green, item.assets["green"], off))
    with np.errstate(divide="ignore", invalid="ignore"):
        idx = {
            "ndvi": (n - r) / (n + r),
            "evi": 2.5 * (n - r) / (n + 6 * r - 7.5 * bl + 1),
            "savi": 1.5 * (n - r) / (n + r + 0.5),
            "ndre": (n - e1) / (n + e1),
            "ndmi": (n - s1) / (n + s1),
            "ndwi": (gr - n) / (gr + n),
        }
    # Valid pixels: real data (DN > 0), clear per SCL, and every normalised-difference denominator comfortably above 0
    # (very dark pixels such as water or deep shadow make ratios meaningless).
    good = ((red > 0) & (nir > 0) & (blue > 0) & (re1 > 0) & (sw1 > 0) & (green > 0) & ((gr + n) > 0.02)
            & ((n + r) > 0.02) & ((n + e1) > 0.02) & ((n + s1) > 0.02)
            & ~np.isin(scl, list(BAD_SCL)))
    for k in idx:
        good &= np.isfinite(idx[k])
        idx[k] = np.clip(idx[k], -1.0, 1.0)

    for pid, geom in parcels:
        g = transform_geom("EPSG:4326", crs, geom)
        inside = geometry_mask([g], out_shape=shape, transform=tr, invert=True, all_touched=False)
        n_in = int(inside.sum())
        if n_in < MIN_PIXELS:
            continue
        ok = inside & good
        frac = float(ok.sum()) / n_in
        if frac < MIN_VALID_FRAC:
            continue
        row = {"parcel_id": pid, "date": item.datetime.date().isoformat()}
        for k in INDEX_FIELDS:
            row[f"{k}_mean"] = round(float(idx[k][ok].mean()), 4)
        # field directions: NDVI per compass sector around the parcel centre
        ys, xs = np.nonzero(inside)
        cy, cx = ys.mean(), xs.mean()
        oy, ox = np.nonzero(ok)
        ang = (np.degrees(np.arctan2(ox - cx, -(oy - cy))) + 360.0) % 360.0     # 0 = north, clockwise
        sec = ((ang + 22.5) // 45).astype(int) % 8
        vals = idx["ndvi"][oy, ox]
        for k, name in enumerate(SECTORS):
            m = sec == k
            row[f"ndvi_{name}"] = round(float(vals[m].mean()), 4) if int(m.sum()) >= MIN_SECTOR_PIXELS else ""
        row.update({"ndvi_std": round(float(idx["ndvi"][ok].std()), 4), "valid_frac": round(frac, 2), "n_pixels": n_in,
                    "scene_id": item.id, "scene_cloud_pct": round(item.properties.get("eo:cloud_cover", -1), 1),
                    "data_source": "real_sentinel2_l2a"})
        rows.append(row)
    return rows


def summarise(obs_by_parcel, as_of):
    """Status rule (documented, deliberately simple):
    baseline = mean NDVI of the observations 15-75 days before the latest one (needs >= 2)
    change   = latest - baseline.  stress: <= -0.10   watch: <= -0.05   normal: otherwise.
    Fewer than 2 baseline observations, or a latest observation older than 45 days -> 'insufficient'."""
    out = {}
    for pid, rows in obs_by_parcel.items():
        rows = sorted(rows, key=lambda r: r["date"])
        if not rows:
            out[pid] = {"status": "insufficient", "reason": "no cloud-free observation in the window"}
            continue
        latest = rows[-1]
        ld = date.fromisoformat(latest["date"])
        base = [r["ndvi_mean"] for r in rows
                if 15 <= (ld - date.fromisoformat(r["date"])).days <= 75]
        age = (as_of - ld).days
        entry = {"latest_date": latest["date"], "latest_ndvi": latest["ndvi_mean"], "age_days": age,
                 "n_obs_year": len(rows), "baseline_ndvi": round(statistics.mean(base), 3) if base else None,
                 "n_baseline": len(base),
                 "series": [{"date": r["date"], "ndvi": r["ndvi_mean"]} for r in rows[-24:]]}
        if len(base) < 2 or age > 45:
            entry.update(status="insufficient", change=None,
                         reason="fewer than 2 baseline observations" if len(base) < 2 else f"latest observation is {age} days old")
        else:
            ch = round(latest["ndvi_mean"] - entry["baseline_ndvi"], 3)
            entry.update(change=ch, status="stress" if ch <= -0.10 else "watch" if ch <= -0.05 else "normal")
        out[pid] = entry
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    as_of = date.fromisoformat(a.as_of)
    start = as_of - timedelta(days=a.days)

    parcels = load_parcels()
    bbox = bbox_of(parcels)
    print(f"{len(parcels)} parcels, bbox {tuple(round(x, 4) for x in bbox)}, {start} .. {as_of}")
    poly = {"type": "Polygon", "coordinates": [[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]]]}
    items = list(Client.open(STAC).search(collections=["sentinel-2-l2a"], intersects=poly,
                                          datetime=f"{start}/{as_of}", query={"eo:cloud_cover": {"lt": 95}},
                                          max_items=600).items())
    # a scene must contain the whole village window, otherwise parcels would be silently cut
    items = [i for i in items if i.bbox[0] <= bbox[0] and i.bbox[1] <= bbox[1] and i.bbox[2] >= bbox[2] and i.bbox[3] >= bbox[3]]
    print(f"{len(items)} candidate scenes")

    rows = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for k, res in enumerate(ex.map(lambda it: process_scene(it, parcels, bbox), items), 1):
            rows.extend(res)
            if k % 10 == 0:
                print(f"  scenes {k}/{len(items)}  observations so far {len(rows)}", flush=True)

    # same parcel + same date from overlapping tiles: keep the one with more valid pixels
    best = {}
    for r in rows:
        k = (r["parcel_id"], r["date"])
        if k not in best or r["valid_frac"] > best[k]["valid_frac"]:
            best[k] = r
    rows = sorted(best.values(), key=lambda r: (r["parcel_id"], r["date"]))

    bad = [r for r in rows if not all(-1.0 <= r[f"{k}_mean"] <= 1.0 for k in INDEX_FIELDS)]
    assert not bad, f"{len(bad)} observations with an index outside -1..1, e.g. {bad[0]}"
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "ndvi_observations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    by = {pid: [] for pid, _ in parcels}
    for r in rows:
        by[r["parcel_id"]].append(r)
    summary = summarise(by, as_of)
    (OUT / "ndvi_summary.json").write_text(json.dumps({
        "as_of": as_of.isoformat(), "generated": datetime.now().isoformat(timespec="seconds"),
        "source": "Sentinel-2 L2A (ESA/Copernicus) via AWS Open Data, Earth Search STAC",
        "note": "Real satellite data at the parcels' coordinates. Crop names, stages and issues in this project are dummy.",
        "rule": summarise.__doc__, "parcels": summary}, indent=1), encoding="utf-8")

    st = {}
    for s in summary.values():
        st[s["status"]] = st.get(s["status"], 0) + 1
    print(f"\n{len(rows)} observations for {len({r['parcel_id'] for r in rows})} parcels -> {OUT}")
    print("status counts:", st)
    for k in INDEX_FIELDS:
        v = [r[f"{k}_mean"] for r in rows]
        print(f"{k.upper():5s} range {min(v):6.2f}..{max(v):5.2f}  median {statistics.median(v):5.2f}")


if __name__ == "__main__":
    main()
