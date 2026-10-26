"""Satellite-pass calendar: every Sentinel-2 and Sentinel-1 pass over Then Malai in the last year, with how many of the
120 parcels had a usable (clear) observation on that date.  Output: backend/data/satellite/pass_calendar.json
Run after build_satellite.py and build_layers.py:  python backend/scripts/build_calendar.py
"""
import csv
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from pystac_client import Client

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_satellite as bs  # noqa: E402

SAT = bs.DATA / "satellite"


def main():
    parcels = bs.load_parcels()
    bbox = bs.bbox_of(parcels)
    end = date.today()
    start = end - timedelta(days=365)
    poly = {"type": "Polygon", "coordinates": [[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]]]}
    covers = lambda i: i.bbox[0] <= bbox[0] and i.bbox[1] <= bbox[1] and i.bbox[2] >= bbox[2] and i.bbox[3] >= bbox[3]

    clear = Counter(r["date"] for r in csv.DictReader(open(SAT / "ndvi_observations.csv", encoding="utf-8")))
    s2 = [i for i in Client.open(bs.STAC).search(collections=["sentinel-2-l2a"], intersects=poly, datetime=f"{start}/{end}", max_items=800).items() if covers(i)]
    s2rows = {}
    for i in s2:
        d = i.datetime.date().isoformat()
        cur = s2rows.get(d)
        row = {"date": d, "scene_cloud_pct": round(i.properties.get("eo:cloud_cover", -1), 1), "parcels_clear": clear.get(d, 0), "scene_id": i.id}
        if cur is None or row["scene_cloud_pct"] < cur["scene_cloud_pct"]:
            s2rows[d] = row

    import planetary_computer as pc
    pcat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
    rad = Counter()
    for r in csv.DictReader(open(SAT / "radar_observations.csv", encoding="utf-8")) if (SAT / "radar_observations.csv").exists() else []:
        rad[r["date"]] += 1
    s1 = [i for i in pcat.search(collections=["sentinel-1-rtc"], intersects=poly, datetime=f"{start}/{end}", max_items=400).items() if covers(i)]
    s1rows = sorted(({"date": i.datetime.date().isoformat(), "orbit": i.properties.get("sat:orbit_state", "?"),
                      "parcels_observed": rad.get(i.datetime.date().isoformat(), 0)} for i in s1), key=lambda r: r["date"])

    out = {"generated": date.today().isoformat(), "window": [start.isoformat(), end.isoformat()],
           "sentinel2": sorted(s2rows.values(), key=lambda r: r["date"]), "sentinel1": s1rows,
           "note": "A Sentinel-2 pass is 'usable' for a parcel only if enough of it is cloud-free. Radar sees through cloud."}
    (SAT / "pass_calendar.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    usable = sum(1 for r in out["sentinel2"] if r["parcels_clear"] > 0)
    print(f"Sentinel-2: {len(out['sentinel2'])} passes, {usable} with at least one clear parcel | Sentinel-1: {len(s1rows)} passes")


if __name__ == "__main__":
    main()
