#!/usr/bin/env python3
"""
Build the Then Malai DEM cache from RAW Copernicus GLO-30 (no Terrarium resampling).

Writes the same files the app already loads:
    public/data/then_malai/dem/dem_display_30m.bin   (int16 little-endian, 482 x 482)
    public/data/then_malai/dem/dem_full_90m.bin      (int16 little-endian, 717 x 741)
    public/data/then_malai/dem/dem_metadata.json     (grid definitions kept IDENTICAL)

Grids and pixel-centre convention are copied from the existing dem_metadata.json so nothing in the
front-end changes. Afterwards run:  npx tsx scripts/regenerate-horizons.ts --write

Requires:  pip install rasterio numpy requests
Data:      AWS Open Data  s3://copernicus-dem-30m  (public, no key)  -  GLO-30 is a DSM
           (top of canopy/buildings), which is what actually casts shade.
"""
import json, math, os, sys, tempfile
import numpy as np
import requests
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling

OUT = os.path.join(os.path.dirname(__file__), "..", "public", "data", "then_malai", "dem")
META_PATH = os.path.join(OUT, "dem_metadata.json")
BASE = "https://copernicus-dem-30m.s3.amazonaws.com"


def tile_name(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def fetch_tiles(grid: dict, tmp: str):
    paths = []
    for la in range(math.floor(grid["lat_min"]), math.floor(grid["lat_max"]) + 1):
        for lo in range(math.floor(grid["lon_min"]), math.floor(grid["lon_max"]) + 1):
            n = tile_name(la, lo)
            dst = os.path.join(tmp, n + ".tif")
            if not os.path.exists(dst):
                url = f"{BASE}/{n}/{n}.tif"
                print("downloading", url)
                r = requests.get(url, timeout=300)
                if r.status_code == 404:      # ocean tile - GLO-30 has no file
                    continue
                r.raise_for_status()
                open(dst, "wb").write(r.content)
            paths.append(dst)
    return paths


def resample(paths, g, method):
    srcs = [rasterio.open(p) for p in paths]
    mosaic, mt = merge(srcs)                       # float32, EPSG:4326
    # pixel (r, c) is the elevation at (lat_max - r*d_lat, lon_min + c*d_lon)  -> centre convention
    dst_tf = from_origin(g["lon_min"] - g["d_lon"] / 2, g["lat_max"] + g["d_lat"] / 2, g["d_lon"], g["d_lat"])
    dst = np.full((g["rows"], g["cols"]), -32768, dtype=np.float32)
    reproject(mosaic[0], dst, src_transform=mt, src_crs="EPSG:4326", dst_transform=dst_tf, dst_crs="EPSG:4326",
              resampling=method, src_nodata=-32767, dst_nodata=-32768)
    dst[dst < -9000] = 0                          # sea / void -> 0 m
    return np.rint(dst).astype("<i2")


def main():
    meta = json.load(open(META_PATH))
    with tempfile.TemporaryDirectory() as tmp:
        # fine grid: GLO-30 is ~0.000278 deg, grid is 0.00027 -> bilinear
        disp = resample(fetch_tiles(meta["display_grid"], tmp), meta["display_grid"], Resampling.bilinear)
        # distant-ridge grid: 0.00081 deg (~3x) -> area-average so crests are not aliased away
        full = resample(fetch_tiles(meta["full_grid"], tmp), meta["full_grid"], Resampling.average)
    disp.tofile(os.path.join(OUT, "dem_display_30m.bin"))
    full.tofile(os.path.join(OUT, "dem_full_90m.bin"))
    meta["source"] = "Copernicus GLO-30 DSM (raw COG, AWS Open Data) - bilinear/average resampled to cache grids"
    meta["display_grid"]["elevation_min_m"] = int(disp.min()); meta["display_grid"]["elevation_max_m"] = int(disp.max())
    meta["full_grid"]["elevation_min_m"] = int(full.min()); meta["full_grid"]["elevation_max_m"] = int(full.max())
    json.dump(meta, open(META_PATH, "w"), indent=2)
    print("done:", disp.shape, full.shape, "now run: npx tsx scripts/regenerate-horizons.ts --write")


if __name__ == "__main__":
    sys.exit(main())
