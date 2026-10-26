"""Build the 16 map layers for Then Malai as georeferenced 8-bit rasters (monthly, cloud-free where possible).

Everything is on one lat/lon grid (EPSG:4326, ~11 m) so the browser can overlay it exactly. Each layer is a PNG plus an
entry in layers.json (value range, units, sources, when to use, caveats).  Grey layers store value = range[0] + (q-1)/254*(range[1]-range[0]),
q = 0 means "no data"; the browser applies any colour palette, opacity, two-date comparison and timelapse.

Layers and where they come from
  real satellite   NDVI EVI SAVI NDRE NDWI NDMI (Sentinel-2 L2A monthly median, cloud/shadow masked), TCI (clearest scene of the month)
  real radar       RVI crop health, RSM relative soil moisture (Sentinel-1 RTC via Planetary Computer, change detection)
  real reference   DEM (Copernicus 30 m), LULC (ESA WorldCover 10 m 2021), SOC (ISRIC SoilGrids 250 m)
  modelled         ET (NDVI-based crop coefficient x Open-Meteo reference ET0)
  our definition   ETCI (contrast-enhanced true colour), HYBRID (TCI + NDVI blend), COLORBLIND (NDVI in a colour-blind-safe palette)
Run: python backend/scripts/build_layers.py [--only static,s2,s1] [--months 12]
"""
import argparse
import io
import json
import math
import statistics
import struct
import sys
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
import requests
from PIL import Image
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import from_bounds
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_satellite as bs  # noqa: E402  (reuses the parcel loader, GDAL settings, band reader and cloud classes)

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "data" / "layers"
RES = 0.0001                                     # degrees, ~11 m
EARTH_SEARCH = bs.STAC
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N06E075_Map.tif"
SOILGRIDS = ("https://maps.isric.org/mapserv?map=/map/soc.map&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=soc_0-5cm_mean"
             "&FORMAT=GEOTIFF_INT16&SUBSET=long({w},{e})&SUBSET=lat({s},{n})"
             "&SUBSETTINGCRS=http://www.opengis.net/def/crs/EPSG/0/4326&OUTPUTCRS=http://www.opengis.net/def/crs/EPSG/0/4326")
CENTRE = (8.91, 77.32)
S1_ENV = {k: v for k, v in bs.GDAL_ENV.items() if k != "CPL_VSIL_CURL_ALLOWED_EXTENSIONS"}   # radar files are .tiff + signed query
MIN_COVER = 0.20                                 # a monthly composite needs >= 20% of the village covered

WC_CLASSES = {10: ("Tree cover", "#006400"), 20: ("Shrubland", "#ffbb22"), 30: ("Grassland", "#ffff4c"), 40: ("Cropland", "#f096ff"),
              50: ("Built-up", "#fa0000"), 60: ("Bare / sparse", "#b4b4b4"), 70: ("Snow and ice", "#f0f0f0"), 80: ("Open water", "#0064c8"),
              90: ("Herbaceous wetland", "#0096a0"), 95: ("Mangroves", "#00cf75"), 100: ("Moss and lichen", "#fae6a0")}

# value ranges for the 8-bit encoding (clipped to these)
RANGES = {"ndvi": (-0.2, 1.0), "evi": (-0.2, 1.0), "savi": (-0.2, 1.0), "ndre": (-0.2, 0.8), "ndwi": (-0.6, 0.6), "ndmi": (-0.4, 0.8),
          "et": (0.0, 8.0), "rvi": (0.0, 1.0), "rsm": (0.0, 1.0)}

LAYER_INFO = {
    "ndvi": dict(name="NDVI", group="Crop health", units="index (-1..1)", source="Sentinel-2 L2A, monthly cloud-masked median", kind="real",
                 what="Greenness: how much healthy leaf is reflecting near-infrared light.",
                 use="First check of crop vigour and the best layer for spotting an early drop (stress) before it is visible to the eye.",
                 caveat="Saturates in dense canopy; bare or flooded paddy reads low even when healthy."),
    "evi": dict(name="EVI", group="Crop health", units="index", source="Sentinel-2 L2A, monthly median", kind="real",
                what="Greenness corrected for atmosphere and soil, less prone to saturating than NDVI.",
                use="Dense, mature canopy (tall sugarcane, maize at tasseling, coconut) where NDVI flattens out.",
                caveat="Noisier than NDVI when the canopy is sparse."),
    "savi": dict(name="SAVI", group="Crop health", units="index", source="Sentinel-2 L2A, monthly median", kind="real",
                 what="Greenness with a correction for bare soil showing between plants.",
                 use="Young crops and thin stands, where exposed soil makes NDVI misleading.", caveat="Less sensitive than NDVI in full canopy."),
    "ndre": dict(name="NDRE", group="Crop health", units="index", source="Sentinel-2 L2A red-edge band, monthly median", kind="real",
                 what="Chlorophyll content, read from the red edge, which keeps responding in dense canopy.",
                 use="Mature crops: spotting nitrogen shortage or early stress inside a dense canopy.", caveat="Red-edge band is 20 m, so it is coarser."),
    "ndwi": dict(name="NDWI", group="Water", units="index", source="Sentinel-2 L2A (green vs NIR), monthly median", kind="real",
                 what="Open water and very wet surfaces: positive over water, negative over vegetation and soil.",
                 use="Finding ponds, tanks and flooded paddy, and checking that a field is really inundated.", caveat="Not a measure of how much water a crop holds (use NDMI)."),
    "ndmi": dict(name="NDMI", group="Water", units="index", source="Sentinel-2 L2A (NIR vs SWIR), monthly median", kind="real",
                 what="Water held inside the leaves (canopy moisture).",
                 use="Irrigation timing and drought stress; it often falls before NDVI does.", caveat="Also responds to leaf structure, so compare a field with itself over time."),
    "et": dict(name="Evapotranspiration", group="Water", units="mm/day", source="Modelled: NDVI-based crop coefficient x Open-Meteo reference ET0", kind="modelled",
               what="Estimated crop water use per day: Kcb = 1.44 x NDVI - 0.1 (clipped 0..1.3) times monthly mean reference ET0.",
               use="Comparing which parts of the village use the most water, and sizing irrigation.",
               caveat="MODELLED, not measured from space. The NDVI-Kcb relation is approximate and ET0 comes from one point (village centre)."),
    "soc": dict(name="Soil organic carbon", group="Soil", units="g/kg (0-5 cm)", source="ISRIC SoilGrids 2.0, 250 m (global model)", kind="real",
                what="Organic carbon in the top 5 cm of soil, a proxy for soil fertility and water holding.",
                use="Planning organic manure and spotting low-fertility zones.", caveat="A global model at 250 m: indicative only, blocky at field scale, not a soil test."),
    "dem": dict(name="DEM (elevation)", group="Terrain and land", units="m above sea level", source="Copernicus GLO-30 DEM, 30 m", kind="real",
                what="Ground height.", use="Drainage, waterlogging risk, and where hill shadow falls.", caveat="A surface model: tree canopy can add a few metres."),
    "lulc": dict(name="Land cover (LULC)", group="Terrain and land", units="class", source="ESA WorldCover 10 m, 2021", kind="real",
                 what="What covers the ground: tree cover, cropland, grassland, built-up, water.",
                 use="Checking which land is farmed and finding forest edges (wildlife pressure).", caveat="A 2021 map: land use may have changed. Mixed pixels are classified by dominant cover."),
    "tci": dict(name="True colour (TCI)", group="Display", units="RGB", source="Sentinel-2 L2A, clearest scene of the month", kind="real",
                what="The village as the human eye would see it from space.", use="Orientation, seeing field boundaries, roads, water and cloud.", caveat="Clouds are shown as they are."),
    "etci": dict(name="Enhanced true colour (ETCI)", group="Display", units="RGB", source="Our definition: TCI with a 2-98% contrast stretch and gamma 0.9", kind="derived",
                 what="True colour with the contrast stretched so field patterns stand out.", use="Seeing differences between fields that look flat in plain true colour.",
                 caveat="OUR OWN display definition; we could not verify what other products call ETCI."),
    "hybrid": dict(name="Hybrid (TCI + NDVI)", group="Display", units="RGB + index", source="Our definition: true colour with NDVI blended at 50%", kind="derived",
                   what="Greenness colours laid over the real picture.", use="Locating exactly where on the ground a weak area sits.", caveat="OUR OWN blend of two real layers."),
    "colorblind": dict(name="Colour-blind safe NDVI", group="Display", units="index", source="Sentinel-2 NDVI in the cividis palette", kind="derived",
                       what="NDVI drawn with a palette that stays readable with red-green colour blindness.", use="Anyone who cannot rely on red-to-green maps.", caveat="Same data as NDVI."),
    "rvi": dict(name="Radar crop health (RVI)", group="Radar", units="index (0..1)", source="Sentinel-1 RTC (VV, VH), monthly median, RVI = 4 VH / (VV + VH)", kind="real",
                what="Canopy structure and biomass from radar, which works through cloud, rain and at night.",
                use="Monsoon months when optical satellites see only cloud.", caveat="Responds to canopy structure, not leaf colour; wet leaves and speckle add noise."),
    "rsm": dict(name="Radar soil moisture (RSM)", group="Radar", units="relative 0 (driest) to 1 (wettest)", source="Sentinel-1 VV change detection (per-pixel dry/wet references, per orbit)", kind="real",
                what="How wet each pixel's surface is relative to its own driest and wettest day of the year.",
                use="Seeing which parts of the village are wet or dry, through cloud.",
                caveat="A RELATIVE index, not volumetric water content. Weaker under dense canopy and forest, and not calibrated to the ground."),
}

W = H = TRANSFORM = BBOX = None


def setup_grid(bbox):
    global W, H, TRANSFORM, BBOX
    BBOX = bbox
    W = int(math.ceil((bbox[2] - bbox[0]) / RES))
    H = int(math.ceil((bbox[3] - bbox[1]) / RES))
    TRANSFORM = from_origin(bbox[0], bbox[3], RES, RES)


def to_grid(arr, src_transform, src_crs, resampling=Resampling.bilinear):
    dst = np.full((H, W), np.nan, dtype="float32")
    reproject(source=arr.astype("float32"), destination=dst, src_transform=src_transform, src_crs=src_crs, dst_transform=TRANSFORM,
              dst_crs="EPSG:4326", resampling=resampling, src_nodata=np.nan, dst_nodata=np.nan)
    return dst


def save_gray(path, arr, rng):
    lo, hi = rng
    q = np.where(np.isfinite(arr), 1 + np.rint((np.clip(arr, lo, hi) - lo) / (hi - lo) * 254), 0).astype("uint8")
    a = np.where(q > 0, 255, 0).astype("uint8")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([q, a]).astype("uint8"), mode="LA").save(path, optimize=True)
    return float(np.isfinite(arr).mean())


def save_rgba(path, rgb, alpha):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([rgb, alpha]).astype("uint8"), mode="RGBA").save(path, optimize=True)


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# ───────────────────────────── static layers ─────────────────────────────
def static_layers(parcels):
    stats = {}
    # DEM: Copernicus 30 m display grid already in the project
    meta = json.loads((ROOT / "dataset" / "then_malai" / "dem" / "dem_metadata.json").read_text())["display_grid"]
    raw = np.frombuffer((ROOT / "dataset" / "then_malai" / "dem" / "dem_display_30m.bin").read_bytes(), dtype="<i2").reshape(meta["rows"], meta["cols"]).astype("float32")
    dem = to_grid(raw, from_origin(meta["lon_min"] - meta["d_lon"] / 2, meta["lat_max"] + meta["d_lat"] / 2, meta["d_lon"], meta["d_lat"]), "EPSG:4326")
    rng = (float(np.nanmin(dem)), float(np.nanmax(dem)))
    RANGES["dem"] = (math.floor(rng[0] / 10) * 10, math.ceil(rng[1] / 10) * 10)
    save_gray(OUT / "dem" / "static.png", dem, RANGES["dem"])
    stats["dem"] = {"min": round(rng[0]), "max": round(rng[1]), "range": list(RANGES["dem"])}

    # LULC: ESA WorldCover (class colours baked into the PNG)
    with rasterio.Env(**bs.GDAL_ENV), rasterio.open(WORLDCOVER) as ds:
        win = from_bounds(*BBOX, transform=ds.transform)
        a = ds.read(1, window=win).astype("float32")
        wt = ds.window_transform(win)
    lulc = to_grid(np.where(a > 0, a, np.nan), wt, "EPSG:4326", Resampling.nearest)
    rgb = np.zeros((H, W, 3), "uint8")
    for code, (_, col) in WC_CLASSES.items():
        rgb[lulc == code] = hex_rgb(col)
    save_rgba(OUT / "lulc" / "static.png", rgb, np.where(np.isfinite(lulc), 235, 0))
    vals, cnt = np.unique(lulc[np.isfinite(lulc)], return_counts=True)
    stats["lulc"] = {WC_CLASSES.get(int(v), (str(int(v)),))[0]: round(float(c) / cnt.sum(), 3) for v, c in zip(vals, cnt)}

    # SOC: SoilGrids WCS, dg/kg -> g/kg
    r = requests.get(SOILGRIDS.format(w=BBOX[0], e=BBOX[2], s=BBOX[1], n=BBOX[3]), timeout=90)
    r.raise_for_status()
    with rasterio.open(io.BytesIO(r.content)) as ds:
        s = ds.read(1).astype("float32") / 10.0
        s[s <= 0] = np.nan
        soc = to_grid(s, ds.transform, ds.crs, Resampling.bilinear)
    RANGES["soc"] = (float(np.floor(np.nanmin(soc))), float(np.ceil(np.nanmax(soc))))
    save_gray(OUT / "soc" / "static.png", soc, RANGES["soc"])
    stats["soc"] = {"min": round(float(np.nanmin(soc)), 1), "max": round(float(np.nanmax(soc)), 1), "median": round(float(np.nanmedian(soc)), 1), "range": list(RANGES["soc"])}

    # SoilGrids pH (water, 0-5 cm; stored x10) for the soil panel
    ph_url = SOILGRIDS.replace("map=/map/soc.map", "map=/map/phh2o.map").replace("COVERAGEID=soc_0-5cm_mean", "COVERAGEID=phh2o_0-5cm_mean")
    rp = requests.get(ph_url.format(w=BBOX[0], e=BBOX[2], s=BBOX[1], n=BBOX[3]), timeout=90)
    rp.raise_for_status()
    with rasterio.open(io.BytesIO(rp.content)) as ds:
        pa = ds.read(1).astype("float32") / 10.0
        pa[(pa <= 2) | (pa > 11)] = np.nan
        ph = to_grid(pa, ds.transform, ds.crs, Resampling.bilinear)
    stats["ph"] = {"min": round(float(np.nanmin(ph)), 1), "max": round(float(np.nanmax(ph)), 1), "median": round(float(np.nanmedian(ph)), 1)}

    # per-parcel context: land cover mix and soil carbon under each polygon
    geo = {}
    for pid, geom in parcels:
        m = geometry_mask([geom], out_shape=(H, W), transform=TRANSFORM, invert=True)
        if not m.any():
            continue
        lv = lulc[m]
        lv = lv[np.isfinite(lv)]
        mix = {WC_CLASSES.get(int(v), (str(int(v)),))[0]: round(float((lv == v).mean()), 2) for v in np.unique(lv)} if lv.size else {}
        geo[pid] = {"land_cover": mix, "dominant": max(mix, key=mix.get) if mix else None,
                    "soc_g_per_kg": round(float(np.nanmean(soc[m])), 1) if np.isfinite(soc[m]).any() else None,
                    "ph_h2o": round(float(np.nanmean(ph[m])), 1) if np.isfinite(ph[m]).any() else None,
                    "elevation_m": round(float(np.nanmean(dem[m]))) if np.isfinite(dem[m]).any() else None}
    (OUT / "parcel_geo.json").write_text(json.dumps({"source": "ESA WorldCover 2021 (10 m), ISRIC SoilGrids (250 m), Copernicus DEM (30 m)", "parcels": geo}, indent=1))
    return stats, lulc, dem


# ───────────────────────────── Sentinel-2 monthly composites ─────────────────────────────
def s2_scene(item):
    """Index arrays (NaN where invalid) on the scene's own UTM grid, plus the TCI window and cloud fraction."""
    with rasterio.Env(**bs.GDAL_ENV):
        with rasterio.open(item.assets["red"].href) as red_ds:
            crs = red_ds.crs
            b = transform_bounds("EPSG:4326", crs, *BBOX)
            win = from_bounds(*b, transform=red_ds.transform).round_offsets().round_lengths()
            red = red_ds.read(1, window=win)
            tr = red_ds.window_transform(win)
            shape = red.shape
            rd = lambda name: bs._read_band(item, name, b, shape, win, red_ds)
            nir, blue, green = rd("nir"), rd("blue"), rd("green")
            re1, sw1 = bs._read_band(item, "rededge1", b, shape), bs._read_band(item, "swir16", b, shape)
        with rasterio.open(item.assets["scl"].href) as ds:
            sw = from_bounds(*b, transform=ds.transform).round_offsets().round_lengths()
            scl = ds.read(1, window=sw, out_shape=shape, resampling=Resampling.nearest)
        with rasterio.open(item.assets["visual"].href) as ds:
            tci = ds.read(window=win, out_shape=(3,) + shape, resampling=Resampling.nearest)
    off = bs.scene_offset(red)
    fl = lambda a, k: np.maximum(bs._reflectance(a, item.assets[k], off), 0.0)
    r, n, bl, e1, s1, gr = fl(red, "red"), fl(nir, "nir"), fl(blue, "blue"), fl(re1, "rededge1"), fl(sw1, "swir16"), fl(green, "green")
    with np.errstate(divide="ignore", invalid="ignore"):
        idx = {"ndvi": (n - r) / (n + r), "evi": 2.5 * (n - r) / (n + 6 * r - 7.5 * bl + 1), "savi": 1.5 * (n - r) / (n + r + 0.5),
               "ndre": (n - e1) / (n + e1), "ndmi": (n - s1) / (n + s1), "ndwi": (gr - n) / (gr + n)}
    good = ((red > 0) & (nir > 0) & (blue > 0) & (re1 > 0) & (sw1 > 0) & (green > 0) & ((n + r) > 0.02) & ((n + e1) > 0.02)
            & ((n + s1) > 0.02) & ((gr + n) > 0.02) & ~np.isin(scl, list(bs.BAD_SCL)))
    for k in idx:
        idx[k] = np.where(good & np.isfinite(idx[k]), np.clip(idx[k], -1, 1), np.nan)
    cloud = float(np.isin(scl, [3, 8, 9, 10]).mean())
    return {"idx": idx, "tr": tr, "crs": crs, "tci": tci, "cloud": cloud, "id": item.id, "date": item.datetime.date().isoformat()}


def et0_monthly(months):
    """Mean daily FAO-56 reference ET0 per month at the village centre (Open-Meteo historical archive)."""
    start, end = f"{months[0]}-01", min(date.today(), date.fromisoformat(f"{months[-1]}-28") + timedelta(days=4)).isoformat()
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
        "latitude": CENTRE[0], "longitude": CENTRE[1], "start_date": start, "end_date": end,
        "daily": "et0_fao_evapotranspiration", "timezone": "Asia/Kolkata"}, timeout=60)
    r.raise_for_status()
    d = r.json()["daily"]
    by = defaultdict(list)
    for t, v in zip(d["time"], d["et0_fao_evapotranspiration"]):
        if v is not None:
            by[t[:7]].append(v)
    return {m: round(statistics.mean(v), 2) for m, v in by.items() if v}


def s2_layers(n_months, parcels):
    cat = Client.open(EARTH_SEARCH)
    end = date.today()
    start = (end.replace(day=1) - timedelta(days=31 * (n_months - 1))).replace(day=1)
    poly = {"type": "Polygon", "coordinates": [[[BBOX[0], BBOX[1]], [BBOX[2], BBOX[1]], [BBOX[2], BBOX[3]], [BBOX[0], BBOX[3]], [BBOX[0], BBOX[1]]]]}
    items = [i for i in cat.search(collections=["sentinel-2-l2a"], intersects=poly, datetime=f"{start}/{end}", query={"eo:cloud_cover": {"lt": 95}}, max_items=800).items()
             if i.bbox[0] <= BBOX[0] and i.bbox[1] <= BBOX[1] and i.bbox[2] >= BBOX[2] and i.bbox[3] >= BBOX[3]]
    by_month = defaultdict(list)
    for i in items:
        by_month[i.datetime.strftime("%Y-%m")].append(i)
    months = sorted(by_month)
    print(f"S2: {len(items)} scenes in {len(months)} months")
    et0 = et0_monthly(months)
    available = defaultdict(list)
    coverage = {}
    for m in months:
        with ThreadPoolExecutor(max_workers=4) as ex:
            scenes = [s for s in ex.map(lambda it: _safe(s2_scene, it), by_month[m]) if s]
        if not scenes:
            continue
        stack = defaultdict(list)
        for s in scenes:
            for k, a in s["idx"].items():
                stack[k].append(to_grid(a, s["tr"], s["crs"]))
        med = {k: np.nanmedian(np.stack(v), axis=0) for k, v in stack.items()}
        cov = float(np.isfinite(med["ndvi"]).mean())
        coverage[m] = round(cov, 2)
        if cov < MIN_COVER:
            print(f"  {m}: only {cov:.0%} clear, skipped")
            continue
        for k in ("ndvi", "evi", "savi", "ndre", "ndwi", "ndmi"):
            save_gray(OUT / k / f"{m}.png", med[k], RANGES[k]); available[k].append(m)
        if m in et0:
            kcb = np.clip(1.44 * med["ndvi"] - 0.1, 0.0, 1.3)
            save_gray(OUT / "et" / f"{m}.png", kcb * et0[m], RANGES["et"]); available["et"].append(m)
        best = min(scenes, key=lambda s: s["cloud"])                       # clearest scene of the month -> true colour
        rgb = np.dstack([to_grid(best["tci"][c].astype("float32"), best["tr"], best["crs"]) for c in range(3)])
        valid = np.isfinite(rgb).all(axis=2) & (np.nan_to_num(rgb).sum(axis=2) > 0)
        rgb8 = np.nan_to_num(rgb).clip(0, 255).astype("uint8")
        save_rgba(OUT / "tci" / f"{m}.png", rgb8, np.where(valid, 255, 0)); available["tci"].append(m)
        lo, hi = np.percentile(rgb8[valid], 2, axis=0), np.percentile(rgb8[valid], 98, axis=0)       # ETCI: contrast stretch + gamma 0.9
        st = np.clip((rgb8.astype("float32") - lo) / np.maximum(hi - lo, 1), 0, 1) ** 0.9
        save_rgba(OUT / "etci" / f"{m}.png", (st * 255).astype("uint8"), np.where(valid, 255, 0)); available["etci"].append(m)
        print(f"  {m}: {len(scenes)} scenes, {cov:.0%} clear (best scene cloud {best['cloud']:.0%}, {best['date']})")
    return available, coverage, et0


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f"  skip {a[0].id}: {type(e).__name__}: {str(e)[:80]}", file=sys.stderr)
        return None


# ───────────────────────────── Sentinel-1 radar ─────────────────────────────
def s1_layers(n_months, parcels):
    import planetary_computer as pc
    cat = Client.open(PC_STAC, modifier=pc.sign_inplace)
    end = date.today()
    start = (end.replace(day=1) - timedelta(days=31 * (n_months - 1))).replace(day=1)
    poly = {"type": "Polygon", "coordinates": [[[BBOX[0], BBOX[1]], [BBOX[2], BBOX[1]], [BBOX[2], BBOX[3]], [BBOX[0], BBOX[3]], [BBOX[0], BBOX[1]]]]}
    items = [i for i in cat.search(collections=["sentinel-1-rtc"], intersects=poly, datetime=f"{start}/{end}", max_items=400).items()
             if i.bbox[0] <= BBOX[0] and i.bbox[1] <= BBOX[1] and i.bbox[2] >= BBOX[2] and i.bbox[3] >= BBOX[3]]
    print(f"S1: {len(items)} RTC scenes")

    def read(item):
        with rasterio.Env(**S1_ENV):
            with rasterio.open(item.assets["vv"].href) as ds:
                crs = ds.crs
                b = transform_bounds("EPSG:4326", crs, *BBOX)
                win = from_bounds(*b, transform=ds.transform).round_offsets().round_lengths()
                vv, tr = ds.read(1, window=win).astype("float32"), ds.window_transform(win)
            with rasterio.open(item.assets["vh"].href) as ds:
                vh = ds.read(1, window=from_bounds(*b, transform=ds.transform).round_offsets().round_lengths(), out_shape=vv.shape).astype("float32")
        for a in (vv, vh):
            a[~np.isfinite(a) | (a <= 0)] = np.nan
        vvf = uniform_filter(np.nan_to_num(vv), 3) / np.maximum(uniform_filter(np.isfinite(vv).astype("float32"), 3), 1e-6)   # 3x3 speckle filter
        vhf = uniform_filter(np.nan_to_num(vh), 3) / np.maximum(uniform_filter(np.isfinite(vh).astype("float32"), 3), 1e-6)
        vvf[~np.isfinite(vv)] = np.nan
        vhf[~np.isfinite(vh)] = np.nan
        return {"vv": to_grid(vvf, tr, crs), "vh": to_grid(vhf, tr, crs), "date": item.datetime.date().isoformat(),
                "orbit": item.properties.get("sat:orbit_state", "?"), "id": item.id}

    with ThreadPoolExecutor(max_workers=4) as ex:
        scenes = [s for s in ex.map(lambda it: _safe(read, it), items) if s]
    # relative soil moisture: per pixel, per orbit direction, (dB - dry)/(wet - dry) with dry/wet = 5th/95th percentile over the year
    by_orbit = defaultdict(list)
    for s in scenes:
        by_orbit[s["orbit"]].append(s)
    for orb, grp in by_orbit.items():
        if len(grp) < 6:
            print(f"  orbit {orb}: only {len(grp)} scenes, RSM skipped for it")
            for s in grp:
                s["rsm"] = np.full((H, W), np.nan, "float32")
            continue
        db = np.stack([10 * np.log10(s["vv"]) for s in grp])
        dry, wet = np.nanpercentile(db, 5, axis=0), np.nanpercentile(db, 95, axis=0)
        for s, d in zip(grp, db):
            s["rsm"] = np.clip((d - dry) / np.maximum(wet - dry, 1.0), 0, 1).astype("float32")   # require >= 1 dB dynamic range
    by_month = defaultdict(list)
    for s in scenes:
        s["rvi"] = 4 * s["vh"] / (s["vv"] + s["vh"])
        by_month[s["date"][:7]].append(s)
    available = defaultdict(list)
    for m in sorted(by_month):
        g = by_month[m]
        for k in ("rvi", "rsm"):
            comp = np.nanmedian(np.stack([s[k] for s in g]), axis=0)
            if np.isfinite(comp).mean() >= MIN_COVER:
                save_gray(OUT / k / f"{m}.png", comp, RANGES[k]); available[k].append(m)
        print(f"  {m}: {len(g)} radar scenes")
    # per-parcel radar series (for the Index Results page)
    import csv
    rows = []
    masks = {pid: geometry_mask([g], out_shape=(H, W), transform=TRANSFORM, invert=True) for pid, g in parcels}
    for s in scenes:
        for pid, m in masks.items():
            if not m.any():
                continue
            rv, rs = s["rvi"][m], s["rsm"][m]
            if np.isfinite(rv).mean() < 0.5:
                continue
            rows.append({"parcel_id": pid, "date": s["date"], "orbit": s["orbit"], "rvi_mean": round(float(np.nanmean(rv)), 4),
                         "rsm_mean": round(float(np.nanmean(rs)), 4) if np.isfinite(rs).any() else "",
                         "vv_db": round(float(10 * np.log10(np.nanmean(s["vv"][m]))), 2), "vh_db": round(float(10 * np.log10(np.nanmean(s["vh"][m]))), 2),
                         "data_source": "real_sentinel1_rtc"})
    rows.sort(key=lambda r: (r["parcel_id"], r["date"]))
    if not rows:
        print("  radar: no usable observations, nothing written")
        return available
    sat = ROOT / "backend" / "data" / "satellite"
    sat.mkdir(parents=True, exist_ok=True)
    with open(sat / "radar_observations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  radar: {len(rows)} parcel observations from {len(scenes)} scenes")
    return available


# ───────────────────────────── manifest + sanity checks ─────────────────────────────
def sanity(lulc):
    """Cross-checks that would expose a wrong formula or a misaligned grid."""
    out = {}
    months = sorted(p.stem for p in (OUT / "ndwi").glob("2*.png"))
    if not months:
        return out
    def load(layer, m):
        im = np.array(Image.open(OUT / layer / f"{m}.png"))
        lo, hi = RANGES[layer]
        v = lo + (im[..., 0].astype("float32") - 1) / 254 * (hi - lo)
        v[im[..., 1] == 0] = np.nan
        return v
    ndwi = np.nanmedian(np.stack([load("ndwi", m) for m in months]), axis=0)
    ndvi = np.nanmedian(np.stack([load("ndvi", m) for m in months]), axis=0)
    for code, label in ((80, "open water"), (10, "tree cover"), (40, "cropland"), (50, "built-up")):
        mask = lulc == code
        if mask.sum() > 50:
            out[label] = {"pixels": int(mask.sum()), "median_ndvi": round(float(np.nanmedian(ndvi[mask])), 2), "median_ndwi": round(float(np.nanmedian(ndwi[mask])), 2)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="static,s2,s1")
    ap.add_argument("--months", type=int, default=12)
    a = ap.parse_args()
    parcels = bs.load_parcels()
    setup_grid(bs.bbox_of(parcels))
    print(f"grid {W}x{H} px at {RES} deg, bbox {tuple(round(x, 4) for x in BBOX)}")
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(a.only.split(","))
    prev = json.loads((OUT / "layers.json").read_text()) if (OUT / "layers.json").exists() else {}
    avail, stats, check = prev.get("months", {}), prev.get("stats", {}), prev.get("sanity", {})
    for k in ("dem", "soc"):                      # ranges computed by an earlier static run
        if isinstance(stats.get(k), dict) and stats[k].get("range"):
            RANGES[k] = tuple(stats[k]["range"])
    lulc = None
    if "static" in only:
        stats, lulc, _ = static_layers(parcels)
        print("static:", stats)
    if "s2" in only:
        av, cov, et0 = s2_layers(a.months, parcels)
        avail.update(av)
        stats["s2_coverage"], stats["et0_mm_day"] = cov, et0
    if "s1" in only:
        avail.update(s1_layers(a.months, parcels))
    if lulc is None:
        with rasterio.Env(**bs.GDAL_ENV), rasterio.open(WORLDCOVER) as ds:
            win = from_bounds(*BBOX, transform=ds.transform)
            arr = ds.read(1, window=win).astype("float32")
            lulc = to_grid(np.where(arr > 0, arr, np.nan), ds.window_transform(win), "EPSG:4326", Resampling.nearest)
    check = sanity(lulc) or check
    print("sanity (median over the year):", check)

    for d in sorted(p for p in OUT.iterdir() if p.is_dir()):
        ms = sorted(f.stem for f in d.glob("2*.png"))
        if ms:
            avail[d.name] = ms
    layers = {}
    for k, info in LAYER_INFO.items():
        layers[k] = {**info, "id": k, "range": RANGES.get(k), "months": avail.get(k, ["static"] if k in ("dem", "lulc", "soc") else []),
                     "needs": {"hybrid": ["tci", "ndvi"], "colorblind": ["ndvi"]}.get(k)}
    layers["hybrid"]["months"] = sorted(set(avail.get("tci", [])) & set(avail.get("ndvi", [])))
    layers["colorblind"]["months"] = avail.get("ndvi", [])
    (OUT / "layers.json").write_text(json.dumps({
        "generated": datetime.now().isoformat(timespec="seconds"),
        "bounds": [[BBOX[1], BBOX[0]], [BBOX[3], BBOX[2]]], "size": [W, H], "resolution_deg": RES,
        "encoding": "grey layers: value = range[0] + (q-1)/254*(range[1]-range[0]); q = 0 means no data",
        "lulc_classes": {str(k): {"name": v[0], "color": v[1]} for k, v in WC_CLASSES.items()},
        "layers": layers, "months": dict(avail), "stats": stats, "sanity": check}, indent=1))
    print("wrote", OUT / "layers.json", "| layers with data:", sum(1 for v in layers.values() if v["months"]))


if __name__ == "__main__":
    main()
