"""
advisory_extras.py — the parts of the personalised farm-advisory dashboard that are not in field_report.py.

Rule: every number is arithmetic on data or a published rule, and anything approximate says so.  No probabilities are invented.
  vigour_classes   share of the parcel in 5 NDVI bands (latest cloud-free composite)
  irrigation_plan  gross water by method efficiency, pump hours, window, rain probability
  soil_panel       record pH / SoilGrids pH / organic carbon / land cover under the parcel; salinity needs a soil test
  evaluate_soil_test   rate a lab soil test (pH, EC, OC, N, P, K) against common Indian limits and adjust the fertiliser dose
  organic_options / schedule_hints   verbatim sentences from the TNAU corpus
  pest_watch       crop watch-list with chemical and organic controls quoted from the corpus (no probabilities)
  yield_outlook    from the parcel's own past seasons (sample data)
  plant_estimate   plants from area and the TNAU recommended spacing
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.transform import from_origin

from app import config
from app.steps import tools

LAYERS = config.DATA_DIR / "layers"

# ── 1. analysis scale ─────────────────────────────────────────────────────────
# Classes from scripts/build_analysis_scale.py (real Sentinel-2 NDVI + NDMI, rule of thumb, not agronomically calibrated).
SCALE_STYLE = {
    "good": ("Good crop health & irrigation", "#2e9e5b"),
    "crop_attention": ("Needs crop-health attention", "#e6c229"),
    "irrigation_attention": ("Needs irrigation attention", "#4a90d9"),
    "critical": ("Critical health & irrigation", "#d1453b"),
    "bare_or_no_crop": ("Bare soil / no crop", "#8b7355"),
}


@lru_cache(maxsize=1)
def _parcel_geo() -> dict:
    """Per-parcel land cover, SoilGrids pH / organic carbon and DEM elevation (scripts/build_layers.py)."""
    f = LAYERS / "parcel_geo.json"
    return json.loads(f.read_text(encoding="utf-8")).get("parcels", {}) if f.exists() else {}


@lru_cache(maxsize=1)
def _analysis_scale() -> dict:
    f = config.DATA_DIR / "satellite" / "analysis_scale.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def vigour_classes(pid: str) -> dict | None:
    d = _analysis_scale()
    p = (d.get("parcels") or {}).get(pid)
    if not p:
        return None
    clear = float(p.get("clear_fraction", 1.0))
    classes = [{"name": name, "share": round(float(p.get(code, 0)) * clear, 3), "color": color} for code, (name, color) in SCALE_STYLE.items()]
    classes.append({"name": "No clear view", "share": round(1 - clear, 3), "color": "#64748b"})
    good = float(p.get("good", 0))
    return {"month": d.get("month"), "classes": classes, "mean_ndvi": None, "good_share": round(good * clear, 3), "pixels": None,
            "basis": (d.get("note") or "") + " Each share is the part of the parcel in that class on the latest monthly cloud-free composite."}


# ── 2. irrigation ─────────────────────────────────────────────────────────────
# Typical application efficiencies (FAO irrigation guidance): share of pumped water that reaches the root zone.
EFFICIENCY = {"drip": 0.90, "sprinkler": 0.75, "flood": 0.60}


def irrigation_plan(parcel: dict, water: dict, method: str = "sprinkler", pump_lps: float = 8.0, rain_prob: dict | None = None) -> dict:
    crop = parcel["crop"]["name"]
    method = "flood" if crop == "Rice" else (method if method in EFFICIENCY else "sprinkler")
    eff = EFFICIENCY[method]
    area = float(parcel.get("area_ha") or 0)
    pump_lps = max(float(pump_lps or 8.0), 0.5)
    days = []
    for d in water["days"]:
        net = d["irrigation_mm"]
        gross = round(net / eff, 1)
        vol = gross * 10 * area                        # 1 mm over 1 ha = 10 m3
        hours = vol * 1000 / (pump_lps * 3600) if vol else 0.0
        days.append({**d, "gross_mm": gross, "volume_m3": round(vol), "pump_hours": round(hours, 1),
                     "rain_probability_pct": (rain_prob or {}).get(d["date"]), "irrigate": net >= 0.5})
    irrigate_days = [d for d in days if d["irrigate"]]
    total = sum(d["volume_m3"] for d in days)
    return {"method": method, "efficiency": eff, "pump_lps": pump_lps, "days": days, "irrigation_days": len(irrigate_days),
            "total_gross_mm": round(sum(d["gross_mm"] for d in days), 1), "total_volume_m3": round(total),
            "total_pump_hours": round(sum(d["pump_hours"] for d in days), 1),
            "best_window": "06:00 to 08:30, or after 17:00 (low evaporation and wind)",
            "basis": f"Net need from FAO-56 water balance divided by a typical {method} efficiency ({int(eff * 100)}%). "
                     "Pump hours = volume / pump discharge (set your own pump rate)."}


# ── 3. soil ───────────────────────────────────────────────────────────────────
def rate_ph(ph: float) -> dict:
    if ph < 5.5: lab, adv = "Strongly acidic", "Liming is usually needed; check the lime requirement with a lab."
    elif ph < 6.5: lab, adv = "Moderately acidic", "Suits many crops; watch phosphorus availability."
    elif ph <= 7.5: lab, adv = "Neutral (best range)", "No correction needed."
    elif ph <= 8.5: lab, adv = "Alkaline", "Prefer acidifying fertilisers and organic matter; zinc and iron may be short."
    else: lab, adv = "Strongly alkaline", "Likely sodic: have it tested, gypsum may be advised."
    return {"value": ph, "class": lab, "advice": adv, "basis": "Common agronomic pH classes."}


def classify_ec(ec: float) -> dict:
    """USDA Handbook 60 salinity classes, EC of the saturation extract in dS/m."""
    for lim, lab in ((2, "Non-saline"), (4, "Very slightly saline"), (8, "Slightly saline"), (16, "Moderately saline")):
        if ec < lim:
            return {"value": ec, "class": lab, "basis": "USDA Handbook 60 salinity classes (dS/m)."}
    return {"value": ec, "class": "Strongly saline", "basis": "USDA Handbook 60 salinity classes (dS/m)."}


def soil_panel(parcel: dict) -> dict:
    pid = parcel["parcel_id"]
    g = _parcel_geo().get(pid, {})
    rec_ph = (parcel.get("soil") or {}).get("ph")
    sg_ph = g.get("ph_h2o")
    return {
        "record_ph": rec_ph, "record_ph_rating": rate_ph(rec_ph) if rec_ph else None,
        "soilgrids_ph": sg_ph, "organic_carbon_g_per_kg": g.get("soc_g_per_kg"),
        "texture": (parcel.get("soil") or {}).get("texture"),
        "drainage": (parcel.get("terrain") or {}).get("drainage_risk"),
        "land_cover_under_parcel": g.get("land_cover"), "dominant_land_cover": g.get("dominant"),
        "salinity": {"status": "not measured", "note": "No dataset gives salinity. Enter your soil-test EC below to classify it."},
        "basis": "Record pH is sample data. SoilGrids pH and organic carbon are a 250 m global model (indicative). Land cover is ESA WorldCover (real).",
    }


# Common Indian soil-fertility rating limits (kg/ha; Subbiah & Asija for N, Olsen for P, NH4OAc for K). Approximate: confirm with your lab.
LIMITS = {"N": (280, 560), "P": (10, 25), "K": (110, 280)}
OC_LIMITS = (0.5, 0.75)        # organic carbon %, low / medium / high
ADJUST = {"low": 1.25, "medium": 1.00, "high": 0.75}


def _rate(v: float, lim: tuple[float, float]) -> str:
    return "low" if v < lim[0] else "medium" if v <= lim[1] else "high"


def evaluate_soil_test(values: dict) -> dict:
    out: dict = {"ratings": {}, "adjustment": {}, "counts": {"needs_attention": 0, "monitor": 0, "optimal": 0}}
    for k in ("N", "P", "K"):
        v = values.get(k)
        if v in (None, ""):
            continue
        r = _rate(float(v), LIMITS[k])
        out["ratings"][k] = {"value": float(v), "rating": r, "limits": LIMITS[k]}
        out["adjustment"][k] = ADJUST[r]
        out["counts"]["needs_attention" if r == "low" else "monitor" if r == "medium" else "optimal"] += 1
    if values.get("OC") not in (None, ""):
        oc = float(values["OC"])
        out["ratings"]["OC"] = {"value": oc, "rating": "low" if oc < OC_LIMITS[0] else "medium" if oc <= OC_LIMITS[1] else "high", "limits": OC_LIMITS}
    if values.get("pH") not in (None, ""):
        out["ph"] = rate_ph(float(values["pH"]))
    if values.get("EC") not in (None, ""):
        out["salinity"] = classify_ec(float(values["EC"]))
    out["basis"] = ("Approximate, commonly used Indian soil-fertility rating limits (available N 280/560, Olsen P 10/25, K 110/280 kg/ha; organic carbon 0.5/0.75%). "
                    "The dose adjustment (low x1.25, medium x1.00, high x0.75) is common practice for blanket recommendations. Confirm with your KVK or lab.")
    return out


# ── 4. corpus sentences (verbatim) ────────────────────────────────────────────
def organic_options(crop: str) -> list[dict]:
    """Curated, verbatim organic / bio nutrient options (controls.py), each with its guide page."""
    from app import controls
    return [{"text": r["text"], "source": r["source"]} for r in controls.organic_nutrients(crop)]


def schedule_hints(crop: str) -> list[dict]:
    return []      # nothing is guessed from the text: split schedules appear only where a curated control exists


def _humidity_signal(pid: str) -> dict | None:
    f = config.WEATHER_FILE
    rows = [r for r in csv.DictReader(open(f, encoding="utf-8", newline="")) if r["parcel_id"] == pid and r["kind"] == "observed"][-7:]
    if not rows:
        return None
    humid = sum(1 for r in rows if float(r["humidity_pct"]) >= 85)
    wet = sum(1 for r in rows if float(r["rain_mm"]) >= 2)
    return {"humid_days": humid, "rainy_days": wet, "favours_fungal": humid >= 3 and wet >= 2,
            "basis": "Last 7 days of the (sample) weather history: days with humidity >= 85% and days with >= 2 mm rain. Fungal diseases are favoured by humid, wet spells."}


def pest_watch(parcel: dict) -> dict:
    from app import controls
    crop = parcel["crop"]["name"]
    pid = parcel["parcel_id"]
    catalog = json.loads((config.DATA_DIR / "issue_catalog.json").read_text(encoding="utf-8"))
    recorded = (parcel.get("observed_issue") or {}).get("code")
    items = []
    for code, spec in controls.CONTROLS.items():
        meta = catalog.get(code, {})
        if spec["crop"] != crop or meta.get("kind") not in ("disease", "pest"):
            continue
        res = controls.controls_for(code)
        if not res["covered"]:
            continue
        groups = {"cultural": [], "organic": [], "chemical": []}
        for it in res["items"]:
            groups["chemical" if it["kind"] in ("chemical", "schedule") else it["kind"] if it["kind"] in groups else "cultural"].append(
                {"text": it["text"], "source": it["source"]})
        items.append({"code": code, "name": meta["label"], "kind": meta["kind"], "severity": meta["severity"], "symptoms": meta["symptoms"],
                      "recorded_on_parcel": code == recorded, "closest": res.get("closest"), **groups})
    items.sort(key=lambda x: (not x["recorded_on_parcel"], x["name"]))
    rec_meta = catalog.get(recorded or "", {})
    no_advice = (rec_meta.get("label") if recorded and rec_meta.get("kind") in ("disease", "pest")
                 and not any(i["code"] == recorded for i in items) else None)

    wc = controls.weed_controls(crop)
    weeds = {"chemical": [], "organic": []}
    for it in wc["items"]:
        weeds["chemical" if it["kind"] in ("chemical", "schedule") else "organic"].append({"text": it["text"], "source": it["source"]})
    return {"watchlist": items[:4], "weeds": weeds, "weeds_note": None if wc["covered"] else wc.get("note"),
            "weather_signal": _humidity_signal(pid), "recorded_without_advice": no_advice,
            "note": controls.CAUTION + " This is a watch-list, not a forecast: no probability is estimated."}


# ── 6. yield outlook and plant count ──────────────────────────────────────────
def yield_outlook(parcel: dict) -> dict | None:
    f = config.DATA_DIR / "history.csv"
    rows = [r for r in csv.DictReader(open(f, encoding="utf-8", newline="")) if r["parcel_id"] == parcel["parcel_id"]]
    if not rows:
        return None
    rows.sort(key=lambda r: r["year"])
    last = rows[-3:]
    vals = [float(r["yield_value"]) for r in last]
    unit = rows[-1]["yield_unit"]
    area = float(parcel.get("area_ha") or 0)
    return {"unit": unit, "last_seasons": [{"year": r["year"], "yield": float(r["yield_value"]), "issue": r["major_issue"]} for r in rows],
            "expected_low": round(min(vals), 1), "expected_mid": round(statistics.mean(vals), 1), "expected_high": round(max(vals), 1),
            "expected_total": round(statistics.mean(vals) * area, 1) if unit.startswith("t/ha") else None,
            "basis": "Range of this parcel's last three seasons (sample data). It is an outlook from past results, not a model forecast; "
                     "this season's weather and health are not used."}


USABLE = 0.90          # assumption: 10% of the area goes to bunds, paths and gaps


def plant_estimate(parcel: dict) -> dict:
    from app import controls
    crop = parcel["crop"]["name"]
    est = controls.plant_estimate(crop, parcel["crop"].get("variety"), float(parcel.get("area_ha") or 0))
    if not est.get("available"):
        return {"available": False, "crop": crop, "note": est.get("note")}
    return {"available": True, "crop": crop, "spacing": est["basis"], "source": est["basis"], "unit": est["unit"], "per_ha": est["per_ha"],
            "plants_at_spacing": est["total"], "plants_usable": round(est["total"] * USABLE),
            "note": est["note"] + " The usable figure takes off 10% for bunds and paths (an assumption)."}
