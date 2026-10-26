"""
field_report.py — Deterministic per-parcel Field Report (no LLM) and the village alerts list.

Answers six farmer questions from data and published formulas only:
  1 How is the crop doing?   real Sentinel-2 NDVI trend at the parcel (labelled: crop labels are dummy)
  2 How much water, when?    FAO-56 water balance: ETc = Kc x ET0, minus effective rain, for the next 7 days
  3 What is the soil like?   pH, texture, drainage from the parcel record
  4 When is harvest?         crop-stage calendar used in this project
  5 What may attack?         the parcel's recorded issue + advisory topics (probabilities are NOT invented)
  6 What fertiliser is short? every TNAU NPK recommendation found for the crop, scaled to the parcel area

Every number carries its basis, and anything dummy or approximate is labelled as such.
"""
from __future__ import annotations

import csv
import json
import logging
import re
import time
from datetime import date, timedelta
from typing import Any

import requests

from app import config
from app import advisory_extras as ex
from app import wildlife
from app.steps import calculator, retrieve, tools

log = logging.getLogger(__name__)

# ── FAO-56 crop coefficients (Allen et al. 1998, Table 12), mapped to this project's stage names ─────────────
# Approximate mid-range values; confirm against the FAO-56 table before quoting them as exact.
KC = {
    "Rice": {"ini": 1.05, "dev": 1.10, "mid": 1.20, "late": 0.90},
    "Maize": {"ini": 0.30, "dev": 0.75, "mid": 1.20, "late": 0.60},
    "Sugarcane": {"ini": 0.40, "dev": 0.80, "mid": 1.25, "late": 0.75},
    "Banana": {"ini": 0.50, "dev": 0.80, "mid": 1.10, "late": 1.00},
    "Coconut": {"ini": 0.95, "dev": 0.95, "mid": 0.95, "late": 0.95},
    # FAO-56 Table 12 values for the nearest listed crop (groundnut; cotton; pulses for blackgram; pepper for chilli; ginger/turmeric type)
    "Groundnut": {"ini": 0.40, "dev": 0.75, "mid": 1.15, "late": 0.60},
    "Cotton": {"ini": 0.35, "dev": 0.75, "mid": 1.15, "late": 0.70},
    "Blackgram": {"ini": 0.40, "dev": 0.70, "mid": 1.10, "late": 0.50},
    "Chilli": {"ini": 0.60, "dev": 0.80, "mid": 1.05, "late": 0.90},
    "Turmeric": {"ini": 0.50, "dev": 0.80, "mid": 1.00, "late": 0.70},
}
PHASE = {
    "Rice": {"Establishment": "ini", "Tillering": "dev", "Panicle Initiation": "mid", "Flowering": "mid",
             "Milk / Dough": "late", "Maturity": "late"},
    "Maize": {"Emergence": "ini", "Vegetative": "dev", "Tasseling": "mid", "Silking": "mid", "Grain Filling": "mid",
              "Maturity": "late"},
    "Sugarcane": {"Germination": "ini", "Tillering": "dev", "Grand Growth": "mid", "Maturity": "late"},
    "Groundnut": {"Emergence": "ini", "Vegetative": "dev", "Flowering": "mid", "Pegging & Pod Formation": "mid", "Pod Development": "mid", "Maturity": "late"},
    "Cotton": {"Emergence": "ini", "Vegetative": "dev", "Squaring": "mid", "Flowering & Boll Formation": "mid", "Boll Development": "mid", "Boll Opening & Picking": "late"},
    "Blackgram": {"Emergence": "ini", "Vegetative": "dev", "Flowering": "mid", "Pod Formation": "mid", "Maturity": "late"},
    "Chilli": {"Establishment": "ini", "Vegetative": "dev", "Flowering": "mid", "Fruiting & Picking": "mid", "Late Picking": "late"},
    "Turmeric": {"Establishment": "ini", "Vegetative": "dev", "Rhizome Bulking": "mid", "Maturity": "late", "Harvest": "late"},
    "Banana": {"Establishment": "ini", "Vegetative": "dev", "Flower Initiation": "mid", "Shooting": "mid",
               "Bunch Development": "mid", "Harvest": "late"},
}
EFFECTIVE_RAIN = 0.8          # share of rainfall counted as available to the crop (simple, documented assumption)
VILLAGE_CENTRE = (8.91, 77.32)
HEAVY_RAIN_3D_MM = 30.0
IRRIGATION_DEFICIT_MM = 25.0
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

_forecast_cache: dict[str, tuple[float, list[dict], str]] = {}
_weather_hist: dict[str, list[dict]] = {}


# ── data access ───────────────────────────────────────────────────────────────
def _parcel(pid: str) -> dict | None:
    tools._load_parcels()
    return tools._PARCEL_BY_ID.get(pid)


def _history_rows(pid: str) -> list[dict]:
    if not _weather_hist:
        with open(config.WEATHER_FILE, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                _weather_hist.setdefault(r["parcel_id"], []).append(r)
    return _weather_hist.get(pid, [])


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def village_forecast(lat: float = VILLAGE_CENTRE[0], lon: float = VILLAGE_CENTRE[1]) -> tuple[list[dict], str]:
    """7-day forecast with ET0. Live Open-Meteo (cached 3 h), otherwise the cached sample forecast."""
    key = f"{lat:.2f},{lon:.2f}"
    hit = _forecast_cache.get(key)
    if hit and time.time() - hit[0] < 3 * 3600:
        return hit[1], hit[2]
    try:
        r = requests.get(config.OPEN_METEO_URL, params={
            "latitude": lat, "longitude": lon, "forecast_days": 7, "timezone": "Asia/Kolkata",
            "daily": "precipitation_sum,precipitation_probability_max,et0_fao_evapotranspiration,temperature_2m_max,temperature_2m_min"},
            timeout=config.OPEN_METEO_TIMEOUT)
        r.raise_for_status()
        d = r.json()["daily"]
        rows = [{"date": d["time"][i], "rain_mm": d["precipitation_sum"][i] or 0.0,
                 "et0_mm": d["et0_fao_evapotranspiration"][i] or 0.0,
                 "rain_prob": (d.get("precipitation_probability_max") or [None] * len(d["time"]))[i],
                 "tmax_c": d["temperature_2m_max"][i], "tmin_c": d["temperature_2m_min"][i]}
                for i in range(len(d["time"]))]
        _forecast_cache[key] = (time.time(), rows, "live")
        return rows, "live"
    except Exception as e:
        log.warning("Open-Meteo forecast failed (%s): using the cached sample forecast", e)
    rows = [r for r in _history_rows("TM-01") if r.get("kind") == "forecast"][:7]
    rows = [{"date": r["date"], "rain_mm": _num(r["rain_mm"]), "et0_mm": _num(r["et0_mm"]),
             "tmax_c": _num(r["tmax_c"]), "tmin_c": _num(r["tmin_c"])} for r in rows]
    return rows, "cached"


def _kc(parcel: dict) -> tuple[float, str]:
    crop = (parcel.get("crop") or {}).get("name", "")
    stage = ((parcel.get("crop") or {}).get("stage") or "").split(" - ")[0]
    if crop == "Coconut":
        return KC["Coconut"]["mid"], "mature"
    phase = PHASE.get(crop, {}).get(stage, "mid")
    return KC.get(crop, KC["Rice"])[phase], phase


# ── 2: water ──────────────────────────────────────────────────────────────────
def water_plan(parcel: dict, fc: list[dict], source: str) -> dict:
    crop = parcel["crop"]["name"]
    kc, phase = _kc(parcel)
    days = []
    for d in fc:
        etc = kc * d["et0_mm"]
        eff = EFFECTIVE_RAIN * d["rain_mm"]
        days.append({"date": d["date"], "et0_mm": round(d["et0_mm"], 1), "etc_mm": round(etc, 1),
                     "rain_mm": round(d["rain_mm"], 1), "irrigation_mm": round(max(etc - eff, 0.0), 1)})
    total = round(sum(x["irrigation_mm"] for x in days), 1)
    m3_per_ha = round(total * 10)  # 1 mm over 1 ha = 10 m3
    area = parcel.get("area_ha") or 0
    note = ("Paddy is kept under standing water: this is crop water use only and excludes seepage and percolation."
            if crop == "Rice" else "Net irrigation need = crop water use minus 80% of forecast rain, floored at zero.")
    return {"crop_coefficient": kc, "growth_phase": phase, "forecast_source": source, "days": days,
            "total_mm_7d": total, "total_m3_per_ha_7d": m3_per_ha, "total_m3_parcel_7d": round(m3_per_ha * area),
            "best_time": "Early morning or evening, when evaporation and wind are lowest.",
            "basis": "FAO-56: ETc = Kc x ET0 (Open-Meteo ET0). Kc values are approximate FAO-56 mid-range figures.",
            "note": note}


# ── 4: harvest ────────────────────────────────────────────────────────────────
def harvest_window(parcel: dict) -> dict:
    crop = parcel["crop"]["name"]
    if crop == "Coconut":
        return {"available": False, "note": "Perennial palm: nuts are picked in rounds, so there is no single harvest date."}
    stages = json.loads((config.DATA_DIR / "crop_stages.json").read_text(encoding="utf-8")).get(crop, [])
    last = stages[-1] if stages else None
    if not last:
        return {"available": False, "note": "No stage calendar for this crop."}
    planted = date.fromisoformat(parcel["crop"]["planting_date"])
    start, end = planted + timedelta(days=last["from_day"]), planted + timedelta(days=last["to_day"])
    return {"available": True, "window_start": start.isoformat(), "window_end": end.isoformat(),
            "days_to_start": (start - date.today()).days, "planted": planted.isoformat(),
            "basis": "Crop-stage calendar used in this project (typical durations). Confirm with the variety's actual duration."}


# ── 6: fertiliser ─────────────────────────────────────────────────────────────
# per-plant doses such as "100:40:140 g of NPK/ tree/ year" (coconut) or "200:30:300 g N: P2O5: K2O / plant" (banana fertigation)
_PER_PLANT = re.compile(
    r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*g\s*(?:of\s*)?(?:NPK|N\s*:\s*P2\s?O5\s*:\s*K2\s?O)?\s*/\s*(tree|palm|plant|clump)(?:\s*/\s*(year|season))?",
    re.IGNORECASE)


def fertilizer_options(parcel: dict) -> dict:
    """Every NPK recommendation the guide gives for this crop (kg/ha, or g per plant converted with the recommended plant density)."""
    retrieve._load_chunks()
    area = float(parcel.get("area_ha") or 0)
    crop = parcel["crop"]["name"]
    dens = ex.plant_estimate(parcel)
    per_ha_plants = dens.get("per_ha") if dens.get("available") else None
    options, seen = [], set()
    for c in retrieve._CHUNKS:
        if c.get("crop") != crop or "nutrient" not in (c.get("topics") or []):
            continue
        text = c.get("text") or ""
        if re.search(r"seed production|Isolation|Land requirement", text):     # seed-crop doses are not the normal commercial dose
            continue
        src = f"{c.get('title', 'TNAU')} p.{c.get('page', '?')}"
        for m in calculator._RATIO.finditer(text):
            ratio = tuple(float(x) for x in m.groups())
            if ratio in seen or len(options) >= 5:
                continue
            seen.add(ratio)
            options.append({"recommendation": f"{m.group(1)}:{m.group(2)}:{m.group(3)} kg N:P2O5:K2O per ha", "source": src,
                            "ratio_per_ha": list(ratio), **calculator.compute(area, *ratio)})
        if per_ha_plants:
            for m in _PER_PLANT.finditer(text):
                g = tuple(float(x) for x in m.groups()[:3])
                if ("g", g) in seen or len(options) >= 5:
                    continue
                seen.add(("g", g))
                kg_ha = tuple(round(v * per_ha_plants / 1000, 2) for v in g)
                unit = m.group(4).lower()
                options.append({"recommendation": f"{m.group(1)}:{m.group(2)}:{m.group(3)} g N:P2O5:K2O per {unit}" + (f" per {m.group(5).lower()}" if m.group(5) else "")
                                                  + f" (= {kg_ha[0]:g}:{kg_ha[1]:g}:{kg_ha[2]:g} kg/ha at {per_ha_plants:,} plants/ha)",
                                "source": src, "ratio_per_ha": list(kg_ha), **calculator.compute(area, *kg_ha)})
    return {"area_ha": area, "options": options,
            "assumptions": "urea 46% N; DAP 18-46-0 (its N is credited); MOP 60% K2O; whole kg; per-plant doses use the recommended plant density",
            "note": ("TNAU gives different recommendations by variety duration, season, age and soil. These are all the ones found "
                     "for this crop; confirm which applies with your KVK." if options else
                     "No NPK recommendation with numbers was found for this crop in the knowledge base.")}


def adjusted_fertilizer(parcel: dict, adjustment: dict) -> list[dict]:
    """TNAU recommendations scaled by soil-test ratings (low x1.25, medium x1.00, high x0.75), then converted to products."""
    area = float(parcel.get("area_ha") or 0)
    out = []
    for o in fertilizer_options(parcel)["options"]:
        n, p, k = o["ratio_per_ha"]
        n2, p2, k2 = n * adjustment.get("N", 1), p * adjustment.get("P", 1), k * adjustment.get("K", 1)
        out.append({"recommendation": o["recommendation"], "source": o["source"],
                    "adjusted_per_ha": f"{n2:g}:{p2:g}:{k2:g}", **calculator.compute(area, n2, p2, k2)})
    return out


# ── 1: satellite ──────────────────────────────────────────────────────────────
def satellite(pid: str) -> dict | None:
    sat = tools._load_satellite()
    e = (sat.get("parcels") or {}).get(pid) if sat else None
    if not e:
        return None
    return {**e, "as_of": sat.get("as_of"), "source": sat.get("source"),
            "label": "Real Sentinel-2 satellite data at this location; the crop name, stage and issue are dummy."}


def satellite_overview() -> dict:
    sat = tools._load_satellite()
    return {"as_of": sat.get("as_of"), "source": sat.get("source"),
            "parcels": {k: {"status": v.get("status"), "ndvi": v.get("latest_ndvi"), "change": v.get("change"),
                            "date": v.get("latest_date")} for k, v in (sat.get("parcels") or {}).items()}}


# ── alerts ────────────────────────────────────────────────────────────────────
def _irrigation_deficit(parcel: dict) -> float | None:
    """Water balance since the last irrigation: sum(Kc*ET0 - 0.8*rain), over the observed sample-weather days."""
    d = int((parcel.get("management") or {}).get("days_since_last_irrigation") or 0)
    if d <= 0:
        return 0.0
    obs = [r for r in _history_rows(parcel["parcel_id"]) if r.get("kind") == "observed"][-d:]
    if not obs:
        return None
    kc, _ = _kc(parcel)
    return round(sum(max(kc * _num(r["et0_mm"]) - EFFECTIVE_RAIN * _num(r["rain_mm"]), 0) for r in obs), 1)


def alerts_for(parcel: dict, fc: list[dict], fc_source: str, sat: dict | None = None) -> list[dict]:
    pid, crop = parcel["parcel_id"], parcel["crop"]["name"]
    out: list[dict] = []

    if sat and sat.get("status") in ("stress", "watch"):
        out.append({"parcel_id": pid, "type": "crop_stress", "severity": "high" if sat["status"] == "stress" else "medium",
                    "title": "Satellite crop-health drop" if sat["status"] == "stress" else "Satellite crop-health dip",
                    "detail": f"NDVI {sat['latest_ndvi']} on {sat['latest_date']} is {abs(sat['change']):.2f} below its recent "
                              f"baseline ({sat['baseline_ndvi']}). This is a stress signal, not a diagnosis.",
                    "action": "Inspect the field this week and photograph any affected plants.", "basis": "Sentinel-2 NDVI (real)"})

    rain3 = round(sum(d["rain_mm"] for d in fc[:3]), 1)
    low_lying = parcel.get("zone") == "valley" or (parcel.get("terrain") or {}).get("waterlogging_susceptibility") == "high"
    if rain3 >= HEAVY_RAIN_3D_MM:
        out.append({"parcel_id": pid, "type": "heavy_rain",
                    "severity": "high" if low_lying and crop != "Rice" else "medium",
                    "title": "Heavy rain forecast",
                    "detail": f"{rain3} mm expected in 3 days ({fc_source} forecast)"
                              + (". Low-lying parcel: waterlogging risk." if low_lying else "."),
                    "action": "Clear drains, and postpone spraying and fertiliser until the rain has passed.",
                    "basis": "Open-Meteo forecast" if fc_source == "live" else "Cached sample forecast"})

    if crop != "Rice":
        deficit = _irrigation_deficit(parcel)
        rain_soon = sum(d["rain_mm"] for d in fc[:3])
        if deficit is not None and deficit >= IRRIGATION_DEFICIT_MM and rain_soon < 10:
            out.append({"parcel_id": pid, "type": "irrigation_due", "severity": "medium", "title": "Irrigation likely due",
                        "detail": f"About {deficit} mm of water used since the last irrigation "
                                  f"({parcel['management']['days_since_last_irrigation']} days ago), little rain in the next 3 days.",
                        "action": "Irrigate in the early morning or evening.",
                        "basis": "FAO-56 water balance on sample weather history"})

    issue = parcel.get("observed_issue") or {}
    if issue.get("code") not in (None, "healthy") and issue.get("severity") in ("moderate", "severe"):
        # a dummy record must not outrank real satellite / weather signals: severe -> medium, moderate -> low
        out.append({"parcel_id": pid, "type": "recorded_issue", "severity": "medium" if issue["severity"] == "severe" else "low",
                    "title": f"Recorded issue: {issue.get('label')}", "detail": f"Severity {issue['severity']}, noted {issue.get('since_days')} days ago (dummy record).",
                    "action": "Ask Cropsy for advice, or upload a photo for a check.", "basis": "Parcel record (dummy)"})
    return out


def all_alerts(min_severity: str = "low") -> dict:
    tools._load_parcels()
    fc, src = village_forecast()
    sat_all = (tools._load_satellite().get("parcels") or {})
    alerts: list[dict] = []
    for p in tools._PARCELS:
        alerts.extend(alerts_for(p, fc, src, sat_all.get(p["parcel_id"])))
    cut = SEVERITY_ORDER[min_severity]
    alerts = sorted([a for a in alerts if SEVERITY_ORDER[a["severity"]] <= cut],
                    key=lambda a: (SEVERITY_ORDER[a["severity"]], a["parcel_id"]))
    by_type: dict[str, int] = {}
    for a in alerts:
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1
    return {"forecast_source": src, "count": len(alerts), "by_type": by_type, "alerts": alerts}



# ── one clear instruction ─────────────────────────────────────────────────────
def instruction(parcel: dict, water: dict, alerts: list[dict], fc: list[dict]) -> dict:
    """Condense satellite trend, alerts, water plan and rain into ONE short instruction (rules, no LLM)."""
    crop = parcel["crop"]["name"]
    steps: list[str] = []
    top = alerts[0] if alerts else None
    rain3 = round(sum(d["rain_mm"] for d in fc[:3]), 1)

    if top and top["severity"] in ("high", "medium") and top["type"] != "recorded_issue":
        steps.append(top["action"])
    if crop == "Rice":
        steps.append("Keep a thin layer of standing water on the field.")
    else:
        need2 = round(sum(d["irrigation_mm"] for d in water["days"][:2]), 1)
        m3 = round(need2 * 10 * (parcel.get("area_ha") or 0))
        if need2 >= 3:
            steps.append(f"Irrigate about {need2} mm over the next 2 days ({m3:,} m3 for the parcel), early morning or evening.")
        else:
            steps.append("No irrigation is needed in the next 2 days: forecast rain and soil water cover the crop's use.")
    if rain3 >= HEAVY_RAIN_3D_MM:
        steps.append(f"Hold spraying and fertiliser until the {rain3} mm of rain has passed.")
    if not steps or (top is None and len(steps) == 1):
        steps.append("No problem signals today; check again after the next satellite pass.")

    if top and top["type"] == "crop_stress":
        head = "Inspect this field this week: satellite greenness is falling."
    elif top and top["type"] == "heavy_rain":
        head = "Prepare for heavy rain: protect the field and delay sprays."
    elif top and top["type"] == "irrigation_due":
        head = "Water the field: it is running dry."
    elif top and top["type"] == "recorded_issue":
        head = f"Check the recorded problem ({top['title'].replace('Recorded issue: ', '')}), then follow the steps below."
    else:
        head = "Field looks steady. Routine care only."
    return {"headline": head, "steps": steps[:3],
            "basis": "Combined from the satellite trend, water balance, rain forecast and parcel record by fixed rules."}

def village_brief() -> dict:
    """One headline for the whole village, from the same alerts (satellite stress first, then rain, then water)."""
    data = all_alerts("low")
    al = data["alerts"]
    stress = sorted({a["parcel_id"] for a in al if a["type"] == "crop_stress" and a["severity"] == "high"})
    watch = sorted({a["parcel_id"] for a in al if a["type"] == "crop_stress" and a["severity"] == "medium"})
    rain = sorted({a["parcel_id"] for a in al if a["type"] == "heavy_rain"})
    dry = sorted({a["parcel_id"] for a in al if a["type"] == "irrigation_due"})
    total = len(tools._PARCELS)
    steps = []
    if stress:
        steps.append(f"Inspect first: {', '.join(stress[:6])}{' and ' + str(len(stress) - 6) + ' more' if len(stress) > 6 else ''} (satellite greenness is falling).")
    if watch:
        steps.append(f"Keep an eye on {len(watch)} more fields with a smaller dip: {', '.join(watch[:5])}{'…' if len(watch) > 5 else ''}.")
    if rain:
        steps.append(f"Heavy rain forecast: clear drains, hold sprays and fertiliser ({len(rain)} fields affected).")
    if dry:
        steps.append(f"{len(dry)} fields look due for irrigation, e.g. {', '.join(dry[:4])}.")
    if not steps:
        steps.append("No field needs urgent attention today.")
    n_act = len(set(stress) | set(rain) | set(dry))
    head = (f"{n_act} of {total} fields need action this week." if n_act else f"All {total} fields look steady this week.")
    return {"headline": head, "steps": steps[:4], "counts": {"stress": len(stress), "watch": len(watch), "heavy_rain": len(rain), "irrigation_due": len(dry), "fields": total},
            "forecast_source": data["forecast_source"],
            "basis": "Real Sentinel-2 trends, the rain forecast and a water balance, combined by fixed rules. Crop labels are dummy."}


# ── the report ────────────────────────────────────────────────────────────────
def build(pid: str, method: str = "sprinkler", pump_lps: float = 8.0) -> dict | None:
    p = _parcel(pid)
    if not p:
        return None
    lat, lon = (p.get("location") or {}).get("lat"), (p.get("location") or {}).get("lon")
    fc, src = village_forecast()
    sat = satellite(pid)
    issue = p.get("observed_issue") or {}
    water = water_plan(p, fc, src)
    alerts_p = sorted(alerts_for(p, fc, src, sat), key=lambda a: SEVERITY_ORDER[a["severity"]])
    return {
        "instruction": instruction(p, water, alerts_p, fc),
        "parcel_id": pid, "village": p.get("village"), "data_source": "dummy parcel record; real satellite and DEM",
        "crop": p["crop"], "area_ha": p.get("area_ha"), "zone": p.get("zone"),
        "health": sat or {"status": "insufficient", "reason": "no satellite summary for this parcel"},
        "water": water,
        "soil": {"texture": (p.get("soil") or {}).get("texture"), "ph": (p.get("soil") or {}).get("ph"),
                 "drainage": (p.get("terrain") or {}).get("drainage_risk"),
                 "waterlogging_susceptibility": (p.get("terrain") or {}).get("waterlogging_susceptibility"),
                 "elevation_m": (p.get("location") or {}).get("elevation_m"),
                 "note": "Salinity and organic carbon are not measured in this dataset."},
        "harvest": harvest_window(p),
        "risks": {"recorded_issue": issue if issue.get("code") != "healthy" else None,
                  "note": "Pest and disease probabilities are not estimated. Ask Cropsy, or upload a photo, for a grounded check."},
        "fertilizer": {**fertilizer_options(p), "organic": ex.organic_options(p["crop"]["name"]), "schedule": ex.schedule_hints(p["crop"]["name"])},
        "vigour": ex.vigour_classes(pid),
        "irrigation": ex.irrigation_plan(p, water, method, pump_lps, {d["date"]: d.get("rain_prob") for d in fc}),
        "soil_panel": ex.soil_panel(p),
        "yield_outlook": ex.yield_outlook(p),
        "plants": ex.plant_estimate(p),
        "watch": ex.pest_watch(p),
        "wildlife": wildlife.parcel_risk(p["crop"]["name"], p.get("zone") or "terrace", {**(p.get("wildlife") or {}), "kind": "dummy"}),
        "field_directions": __import__("app.indices", fromlist=["field_directions"]).field_directions(pid),
        "alerts": alerts_p,
        "forecast_source": src,
    }
