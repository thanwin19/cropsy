"""Generate the full Then Malai village: ~120 parcel polygons + one CSV row each.

* 16 anchor parcels (TM-01..16) keep their real coordinates; polygons come from the frontend's
  hard-coded quads where they exist, otherwise a small quad around the point.
* New parcels (TM-17..) are placed by blue-noise sampling inside the village box on cultivable land
  (DEM elevation from the real Copernicus grid), zoned valley / terrace / foothill.
Output: backend/data/village_geometry.geojson (geometry + zone + crop for new parcels; build_dataset.py completes it)
Run: python backend/scripts/build_village.py
"""
import csv
import json
import math
import random
import re
import struct
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEM_DIR = ROOT / "dataset" / "then_malai" / "dem"
TSX = (Path(__file__).resolve().parent / "legacy" / "ThenMalaiMapView.old.tsx")   # kept copy of the old front end's map file (source of the 16 anchor parcels)
TSX = TSX if TSX.exists() else None
OUT = ROOT / "backend" / "data"
SEED = 36
AS_OF = date(2026, 10, 3)
TARGET = 120
BOX = dict(lat_min=8.884, lat_max=8.928, lon_min=77.298, lon_max=77.352)
MIN_SEP_M = 300
M_LAT = 111_000.0
M_LON = 111_000.0 * math.cos(math.radians(8.91))

# ---- real DEM --------------------------------------------------------------------------
meta = json.loads((DEM_DIR / "dem_metadata.json").read_text())["display_grid"]
raw = (DEM_DIR / "dem_display_30m.bin").read_bytes()
GRID = struct.unpack(f"<{meta['rows'] * meta['cols']}h", raw)


def elev(lat, lon):
    r = round((meta["lat_max"] - lat) / meta["d_lat"])
    c = round((lon - meta["lon_min"]) / meta["d_lon"])
    r = min(max(r, 0), meta["rows"] - 1)
    c = min(max(c, 0), meta["cols"] - 1)
    return GRID[r * meta["cols"] + c]


def area_ha(ring):
    pts = [((lon - ring[0][1]) * M_LON, (lat - ring[0][0]) * M_LAT) for lat, lon in ring]
    s = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return abs(s) / 2 / 10_000


def quad(lat, lon, w_m, h_m, rot_deg, rnd):
    th = math.radians(rot_deg)
    ring = []
    for dx, dy in [(-w_m / 2, -h_m / 2), (w_m / 2, -h_m / 2), (w_m / 2, h_m / 2), (-w_m / 2, h_m / 2)]:
        dx += rnd.uniform(-6, 6)
        dy += rnd.uniform(-6, 6)
        x = dx * math.cos(th) - dy * math.sin(th)
        y = dx * math.sin(th) + dy * math.cos(th)
        ring.append((round(lat + y / M_LAT, 6), round(lon + x / M_LON, 6)))
    return ring


# ---- anchors ---------------------------------------------------------------------------
SRC_CSV = ROOT / "dataset" / "then_malai" / "then_malai_parcels.csv"
anchors = [{"parcel_id": r["survey_no"], "lat": float(r["lat"]), "lon": float(r["lon"]),
            "elev": float(r["elevation_m"])} for r in csv.DictReader(open(SRC_CSV, encoding="utf-8"))]
tsx_polys = {}
if TSX:
    txt = TSX.read_text(encoding="utf-8")
    ids = [(m.start(), m.group(1)) for m in re.finditer(r'id:\s*"(TM-\d+)"', txt)]
    for k, (pos, pid) in enumerate(ids):
        end = ids[k + 1][0] if k + 1 < len(ids) else len(txt)
        m = re.search(r"coords:\s*\[(.*?)\]\s*as", txt[pos:end], re.S)
        if m:
            pts = re.findall(r"\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]", m.group(1))
            if len(pts) >= 3:
                tsx_polys[pid] = [(float(a), float(b)) for a, b in pts]

# ---- zone helpers ----------------------------------------------------------------------
OWNERS = ["Arumugam", "Chellapandi", "Durairaj", "Esakkimuthu", "Ganesan", "Hariharan", "Isakkiammal", "Jeyalakshmi",
          "Karuppasamy", "Lakshmanan", "Maariyappan", "Nagarajan", "Pechiammal", "Rajendran", "Selvam", "Thangaraj",
          "Udhayakumar", "Velusamy", "Alagu", "Balasubramanian", "Chandrasekar", "Dhanalakshmi", "Eswari", "Murugesan"]
INITIALS = "ABCDEGKMNPRSTV"
CROPS = {"valley": [("Rice", .45), ("Banana", .2), ("Sugarcane", .25), ("Maize", .1)],
         "terrace": [("Banana", .3), ("Coconut", .3), ("Maize", .25), ("Sugarcane", .15)],
         "foothill": [("Coconut", .6), ("Banana", .2), ("Maize", .2)]}
VARIETY = {"Rice": "ADT 45", "Banana": None, "Sugarcane": "Co 86032", "Maize": "Hybrid CO 6", "Coconut": "West Coast Tall"}
DAP = {"Rice": (5, 100), "Banana": (20, 320), "Sugarcane": (20, 330), "Maize": (8, 100)}
SOIL = {"valley": ("Clay Loam", (6.4, 7.2), (28, 36, 34)), "terrace": ("Sandy Clay Loam", (5.9, 6.5), (44, 25, 31)),
        "foothill": ("Sandy Loam", (5.5, 6.2), (58, 24, 18))}
DRAIN = {"valley": ("high_waterlogging_risk", "valley_basin"), "terrace": ("moderate_drainage", "mid_terrace"),
         "foothill": ("fast_drainage_erosion_risk", "foothill_slope")}


def zone_of(e):
    return "valley" if e < 168 else "terrace" if e < 195 else "foothill"


def pick(rnd, opts):
    r, acc = rnd.random(), 0
    for name, w in opts:
        acc += w
        if r <= acc:
            return name
    return opts[-1][0]


def main():
    rnd = random.Random(SEED)
    feats = []
    taken = []  # (lat, lon)

    def far_enough(lat, lon):
        return all(math.hypot((lat - a) * M_LAT, (lon - b) * M_LON) >= MIN_SEP_M for a, b in taken)

    # anchors
    for p in anchors:
        lat, lon = p["lat"], p["lon"]
        ring = tsx_polys.get(p["parcel_id"]) or quad(lat, lon, 150, 120, rnd.uniform(-20, 20), rnd)
        taken.append((lat, lon))
        feats.append(dict(id=p["parcel_id"], anchor=True, ring=ring, lat=lat, lon=lon, base=None, elev=p["elev"]))

    tries = 0
    n = len(anchors)
    while n < TARGET and tries < 60_000:
        tries += 1
        lat = rnd.uniform(BOX["lat_min"], BOX["lat_max"])
        lon = rnd.uniform(BOX["lon_min"], BOX["lon_max"])
        e = elev(lat, lon)
        if e > 235 or e < 120 or not far_enough(lat, lon):
            continue
        taken.append((lat, lon))
        n += 1
        feats.append(dict(id=f"TM-{n:02d}" if n < 100 else f"TM-{n}", anchor=False, lat=lat, lon=lon, base=None,
                          ring=quad(lat, lon, rnd.uniform(110, 210), rnd.uniform(90, 170), rnd.uniform(-30, 30), rnd)))
    if n < TARGET:
        print(f"WARNING: only placed {n} parcels")

    geo, rows = [], []
    for f in feats:
        base = f["base"]
        e = elev(f["lat"], f["lon"])
        z = zone_of(f["elev"] if f["anchor"] else e)
        if f["anchor"]:
            z = zone_of(f["elev"])
            props = dict(parcel_id=f["id"], anchor=True, zone=z, village="Then Malai", elevation_m=f["elev"])
        else:
            crop = pick(rnd, CROPS[z])
            variety = VARIETY[crop] or rnd.choice(["Grand Naine", "Nendran"])
            if crop == "Coconut":
                plant = date(rnd.randint(2012, 2020), rnd.randint(1, 12), rnd.randint(1, 28))
            else:
                plant = AS_OF - timedelta(days=rnd.randint(*DAP[crop]))
            tex, (ph_lo, ph_hi), (sa, si, cl) = SOIL[z]
            owner = f"{rnd.choice(INITIALS)}. {rnd.choice(OWNERS)}"
            props = dict(parcel_id=f["id"], anchor=False, zone=z, village="Then Malai", crop=crop, variety=variety,
                         stage=None, planting_date=plant.isoformat(), soil_texture=tex,
                         soil_ph=round(rnd.uniform(ph_lo, ph_hi), 1), elevation_m=e,
                         area_ha=round(area_ha(f["ring"]), 2), owner=owner,
                         patta_no=f"TM-{100 + int(re.sub(r'[^0-9]', '', f['id']))}",
                         issue_code=None, issue=None, data_source="dummy")
            props.update(sand_pct=sa + rnd.randint(-4, 4), silt_pct=si + rnd.randint(-3, 3), clay_pct=cl + rnd.randint(-3, 3))
        props["drainage_risk"], props["terrain_zone"] = DRAIN[z]
        props["lat"], props["lon"] = round(f["lat"], 6), round(f["lon"], 6)
        ring = [[lon, lat] for lat, lon in f["ring"]]
        ring.append(ring[0])
        geo.append({"type": "Feature", "id": f["id"], "properties": props,
                    "geometry": {"type": "Polygon", "coordinates": [ring]}})
        rows.append(props)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "village_geometry.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "name": "then_malai_parcels", "features": geo}, ensure_ascii=False),
        encoding="utf-8")
    # report
    from collections import Counter
    print("parcels:", len(rows), "| polygons from frontend:", len(tsx_polys), "| tries:", tries)
    print("zone:", dict(Counter(r["zone"] for r in rows)))
    print("crop:", dict(Counter(r.get("crop", "anchor") for r in rows)))
    print("new-parcel area ha:", round(sum(r.get("area_ha", 0) for r in rows), 1))


if __name__ == "__main__":
    main()
