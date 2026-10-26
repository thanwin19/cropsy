"""
spread.py: village-scale spread-risk model for wind-borne crop diseases (rice blast, groundnut rust, banana sigatoka, sugarcane rust).

When one parcel has an airborne disease, this ranks the OTHER parcels by how likely they are to be exposed in the next 72 hours, from
  1  geometry     distance and bearing from the infected parcel to every susceptible parcel (checked a second, independent way)
  2  wind         hourly wind speed and direction (Open-Meteo forecast, or a value the user types in)
  3  biology      the disease's weather window (temperature, humidity) and the crop stage's susceptibility
  4  scoring      hourly exposure = distance kernel x downwind alignment x wind factor x weather favourability x stage; summed over the hours
  5  alert        (separate, on demand) a village message in Tamil and English written from the result

HONESTY NOTES (shown in the app):
  * It is a transparent risk-ranking model, not a validated forecast. Its numbers are scenario assumptions, not measurements.
  * TNAU pages say these diseases spread by wind-borne spores and like moist weather. They do NOT give a dispersal distance or a
    temperature/humidity threshold for blast, so those parameters are marked "assumption" and can be changed.
  * Parcel positions, crops and recorded issues in this demo village are dummy data; the wind and weather are real forecast data.
  * "Hours to threshold" means hours until the exposure index first reaches 50; it is not the time symptoms will appear.
All scoring is plain arithmetic: the language model is only used to write the alert text.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone

import requests

from app import config
from app.steps import tools

THRESHOLD = 50.0            # risk index at which exposure is called "likely"
HOURS = 72
BACKGROUND = 0.08           # share of exposure that does not depend on wind direction (turbulence, rain splash, people and tools)
C = 0.09                    # converts summed exposure to a 0..100 index: 200 m downwind for 72 favourable hours gives about 95

TNAU_BLAST = {"title": "TNAU Agritech: Rice diseases, Blast", "url": "https://agritech.tnau.ac.in/crop_protection/rice_diseases/rice_1.html"}
TNAU_BLAST_ES = {"title": "TNAU Agritech Expert System: Blast (Pyricularia oryzae)", "url": "https://agritech.tnau.ac.in/expert_system/paddy/cpdisblast.html"}
TNAU_RUST = {"title": "TNAU Agritech: Groundnut rust (Puccinia arachidis)", "url": "https://agritech.tnau.ac.in/crop_protection/groundnut_diseases/groundnut_d3.html"}
TNAU_BANANA = {"title": "TNAU Agritech Banana Expert System: crop protection", "url": "https://agritech.tnau.ac.in/expert_system/banana/cropprotection.html"}
ASSUME = {"title": "Model assumption (general plant-pathology knowledge, not a TNAU figure)", "url": ""}

DISEASES: dict[str, dict] = {
    "rice_blast": {"label": "Rice blast", "crop": "Rice", "scale_m": 250, "max_m": 1200, "t": (22, 30), "rh_min": 88,
                   "stage_weight": {"Establishment": 0.7, "Tillering": 1.0, "Panicle Initiation": 1.0, "Flowering": 0.8, "Milk / Dough": 0.4, "Maturity": 0.1},
                   "evidence": [("Spores spread by wind to other rice plants, over great distances", TNAU_BLAST_ES, "TNAU (qualitative)"),
                                ("Lesions enlarge under moist weather", TNAU_BLAST, "TNAU (qualitative)"),
                                ("Weather window 22-30 C and relative humidity at least 88%", ASSUME, "assumption"),
                                ("Spore reach: most exposure within about 250 m, none counted beyond 1.2 km", ASSUME, "assumption"),
                                ("Stage susceptibility (tillering and panicle initiation highest)", ASSUME, "assumption")]},
    "groundnut_rust": {"label": "Groundnut rust", "crop": "Groundnut", "scale_m": 220, "max_m": 1000, "t": (20, 28), "rh_min": 85,
                       "stage_weight": {"Emergence": 0.5, "Vegetative": 0.8, "Flowering": 1.0, "Pegging & Pod Formation": 1.0, "Pod Development": 0.7, "Maturity": 0.2},
                       "evidence": [("Spores move by wind, rain splash and farm implements", TNAU_RUST, "TNAU (qualitative)"),
                                    ("Favourable: relative humidity above 85%, heavy rain, 20-25 C (TNAU entry for the same fungus on gingelly)", TNAU_RUST, "TNAU (other crop)"),
                                    ("Spore reach: most exposure within about 220 m", ASSUME, "assumption")]},
    "banana_sigatoka": {"label": "Banana sigatoka leaf spot", "crop": "Banana", "scale_m": 150, "max_m": 700, "t": (21, 31), "rh_min": 85,
                        "stage_weight": {"Establishment": 0.6, "Vegetative": 1.0, "Flower Initiation": 0.9, "Shooting": 0.8, "Bunch Development": 0.6, "Harvest": 0.2},
                        "evidence": [("Infection needs high humidity or a wet leaf; waterlogging raises humidity", TNAU_BANANA, "TNAU (qualitative)"),
                                     ("Spores spread by wind and rain splash over short distances", ASSUME, "assumption"),
                                     ("Weather window 21-31 C and relative humidity at least 85%", ASSUME, "assumption")]},
    "cane_rust": {"label": "Sugarcane rust", "crop": "Sugarcane", "scale_m": 220, "max_m": 1000, "t": (20, 30), "rh_min": 80,
                  "stage_weight": {"Germination": 0.4, "Tillering": 0.9, "Grand Growth": 1.0, "Maturity": 0.3},
                  "evidence": [("Rust spores are wind-borne", ASSUME, "assumption"), ("Weather window 20-30 C and relative humidity at least 80%", ASSUME, "assumption")]},
}
# Cordana leaf spot: the TNAU banana pages in our knowledge base have no entry for it, so every figure below is general plant-pathology knowledge, labelled as such.
DISEASES["banana_cordana"] = {"label": "Banana Cordana leaf spot", "crop": "Banana", "scale_m": 120, "max_m": 600, "t": (20, 30), "rh_min": 85,
                              "stage_weight": {"Establishment": 0.6, "Vegetative": 1.0, "Flower Initiation": 0.9, "Shooting": 0.8, "Bunch Development": 0.6, "Harvest": 0.2},
                              "evidence": [("Spores spread by wind and rain splash over short distances (general plant pathology; TNAU's banana pages in this knowledge base have no Cordana entry)",
                                            {"title": "General plant-pathology knowledge, regional source, not TNAU", "url": ""}, "general knowledge, not TNAU"),
                                           ("Weather window 20-30 C and relative humidity at least 85%", ASSUME, "assumption"),
                                           ("Spore reach: most exposure within about 120 m", ASSUME, "assumption")]}
AIRBORNE = {c: d for c, d in DISEASES.items()}
_cache: dict = {}


# ── geometry (two independent ways, so the verifier can compare them) ──────────────────────────────────────────────
def haversine_bearing(lat1, lon1, lat2, lon2) -> tuple[float, float]:
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 6371000 * 2 * math.asin(math.sqrt(a))
    b = math.degrees(math.atan2(math.sin(dl) * math.cos(p2), math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360
    return d, b


def flat_distance_bearing(lat1, lon1, lat2, lon2) -> tuple[float, float]:
    """Local flat-earth (east/north metres): a different formula used only to cross-check the first one."""
    north = (lat2 - lat1) * 111_320.0
    east = (lon2 - lon1) * 111_320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(east, north), math.degrees(math.atan2(east, north)) % 360


def angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def compass(deg: float) -> str:
    return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][int((deg % 360) / 22.5 + 0.5) % 16]


# ── wind and weather ───────────────────────────────────────────────────────────────────────────────────────────────
def _hourly(lat: float, lon: float) -> dict | None:
    key = (round(lat, 1), round(lon, 1))      # the weather model grid is about 10 km, so the whole village shares one lookup
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < (900 if hit[1] else 120):      # a failed lookup is remembered for 2 minutes, so 23 sources do not each wait for a timeout
        return hit[1]
    try:
        r = requests.get(config.OPEN_METEO_URL, params={"latitude": lat, "longitude": lon, "forecast_days": 4, "timezone": "Asia/Kolkata",
                                                         "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"}, timeout=5)
        r.raise_for_status()
        h = r.json()["hourly"]
        now = datetime.now().strftime("%Y-%m-%dT%H:00")
        i0 = next((i for i, t in enumerate(h["time"]) if t >= now), 0)
        out = {k: h[k][i0:i0 + HOURS] for k in ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m")}
        out["start"] = h["time"][i0]
        if min(len(v) for k, v in out.items() if k != "start") < 24:
            _cache[key] = (time.time(), None)
            return None
        _cache[key] = (time.time(), out)
        return out
    except Exception:  # noqa: BLE001
        _cache[key] = (time.time(), None)
        return None


def build_weather(lat: float, lon: float, wind_speed_kmh: float | None = None, wind_from_deg: float | None = None, favourable: bool = False) -> dict:
    """Hourly arrays for the next 72 h plus where they came from. Typed-in wind replaces the forecast wind; 'favourable' assumes perfect disease weather."""
    live = _hourly(lat, lon)
    notes = []
    if live:
        T, RH, WS, WD = (list(live[k]) for k in ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m"))
        src = "live Open-Meteo hourly forecast from " + live["start"]
    else:
        n = HOURS
        T, RH, WS, WD = [27.0] * n, [85.0] * n, [10.0] * n, [225.0] * n
        src = "NOT AVAILABLE: assumed 27 C, 85% humidity, 10 km/h from the south-west (225 degrees)"
        notes.append("The live forecast could not be reached, so assumed weather is used. Treat the result as a scenario only.")
    if wind_speed_kmh is not None:
        WS = [float(wind_speed_kmh)] * len(WS)
        src += " | wind speed typed in"
    if wind_from_deg is not None:
        WD = [float(wind_from_deg) % 360] * len(WD)
        src += " | wind direction typed in"
    return {"T": T, "RH": RH, "WS": WS, "WD": WD, "source": src, "notes": notes, "favourable": favourable, "typed": wind_speed_kmh is not None or wind_from_deg is not None}


def _fav(d: dict, t: float, rh: float, assume: bool) -> float:
    if assume:
        return 1.0
    lo, hi = d["t"]
    tf = 1.0 if lo <= t <= hi else max(0.0, 1 - (lo - t if t < lo else t - hi) / 5.0)
    rf = max(0.0, min(1.0, (rh - (d["rh_min"] - 10)) / 10.0))
    return tf * rf


def _mean_dir(dirs: list[float], speeds: list[float]) -> float:
    x = sum(s * math.sin(math.radians(a)) for a, s in zip(dirs, speeds))
    y = sum(s * math.cos(math.radians(a)) for a, s in zip(dirs, speeds))
    return math.degrees(math.atan2(x, y)) % 360


# ── the model ──────────────────────────────────────────────────────────────────────────────────────────────────────
def forecast(source_pid: str, disease_code: str | None = None, wind_speed_kmh: float | None = None, wind_from_deg: float | None = None, favourable: bool = False) -> dict:
    t0 = time.perf_counter()
    tools._load_parcels()
    ps = {p["parcel_id"]: p for p in tools._PARCELS}
    src = ps.get(source_pid)
    if not src:
        raise ValueError(f"unknown parcel {source_pid}")
    code = disease_code or (src.get("observed_issue") or {}).get("code")
    if code not in AIRBORNE:
        # "what if it were infected": a parcel of a modelled crop with no recorded wind-borne disease uses that crop's main modelled disease
        crop_name = (src.get("crop") or {}).get("name")
        code = next((c for c, dd in AIRBORNE.items() if dd["crop"] == crop_name), code)
    if code not in AIRBORNE:
        raise ValueError(f"{source_pid}'s recorded problem is not one of the wind-borne diseases this model covers ({', '.join(AIRBORNE)})")
    d = AIRBORNE[code]
    slat, slon = src["location"]["lat"], src["location"]["lon"]
    w = build_weather(slat, slon, wind_speed_kmh, wind_from_deg, favourable)
    n = len(w["WS"])
    fav_hours = [_fav(d, w["T"][h], w["RH"][h], favourable) for h in range(n)]
    rows = []
    for pid, p in ps.items():
        if pid == source_pid:
            continue
        crop = (p.get("crop") or {}).get("name")
        stage = str((p.get("crop") or {}).get("stage", "")).split(" - ")[0]
        loc = p["location"]
        dist, bear = haversine_bearing(slat, slon, loc["lat"], loc["lon"])
        row = {"parcel_id": pid, "crop": crop, "stage": stage, "distance_m": round(dist), "bearing_deg": round(bear), "bearing_compass": compass(bear)}
        if crop != d["crop"] or dist > d["max_m"]:
            row.update({"risk": 0.0, "level": "none", "hours_to_threshold": None, "downwind": False, "alignment_mean": 0.0,
                        "why": ("a different crop, not affected by " + d["label"]) if crop != d["crop"] else f"beyond the {d['max_m']} m spore reach used by the model"})
            rows.append(row)
            continue
        sw = d["stage_weight"].get(stage, 0.6)
        kern = math.exp(-dist / d["scale_m"])
        e_cum, hit_h, aligns, tl = 0.0, None, [], [0.0]
        for h in range(n):
            move_to = (w["WD"][h] + 180) % 360                       # wind direction is where it blows FROM; the air moves the opposite way
            a = max(0.0, math.cos(math.radians(angle_diff(bear, move_to)))) ** 2
            aligns.append(a)
            wf = 0.25 + 0.75 * min(1.0, w["WS"][h] / 15.0)
            e_cum += kern * (BACKGROUND + (1 - BACKGROUND) * a) * wf * fav_hours[h]
            if hit_h is None and 100 * (1 - math.exp(-C * sw * e_cum)) >= THRESHOLD:
                hit_h = h + 1
            if (h + 1) % 3 == 0:
                tl.append(round(100 * (1 - math.exp(-C * sw * e_cum)), 1))      # risk after each 3 hours: the live demo plays this
        risk = round(100 * (1 - math.exp(-C * sw * e_cum)), 1)
        am = sum(aligns) / n
        level = "red" if risk >= 70 else "amber" if risk >= THRESHOLD else "watch" if risk >= 20 else "low"
        why = (f"{round(dist)} m to the {compass(bear)} of {source_pid}; "
               f"wind blows toward the {compass(_mean_dir(w['WD'], w['WS']) + 180)} on average ({'downwind' if am >= 0.35 else 'not mainly downwind'}); "
               f"{sum(1 for f in fav_hours if f >= 0.6)} of {n} hours have favourable weather; {stage or 'stage unknown'} susceptibility {sw:g}")
        row.update({"risk": risk, "level": level, "hours_to_threshold": hit_h, "downwind": am >= 0.35, "alignment_mean": round(am, 2), "stage_weight": sw, "exposure": round(e_cum, 2), "why": why, "timeline": tl})
        rows.append(row)
    rows.sort(key=lambda r: (-r["risk"], r["distance_m"]))
    ver = verify_geometry(source_pid, rows, ps, w, d)
    dom_from = _mean_dir(w["WD"], w["WS"])
    return {"source": {"parcel_id": source_pid, "crop": src["crop"]["name"], "stage": str(src["crop"].get("stage", "")).split(" - ")[0], "lat": slat, "lon": slon,
                       "disease_code": code, "disease": d["label"]},
            "disease": {"label": d["label"], "scale_m": d["scale_m"], "max_m": d["max_m"], "weather_window": f"{d['t'][0]}-{d['t'][1]} C, humidity at least {d['rh_min']}%",
                        "evidence": [{"claim": c, "source": s["title"], "url": s["url"], "kind": k} for c, s, k in d["evidence"]]},
            "wind": {"source": w["source"], "mean_speed_kmh": round(sum(w["WS"]) / n, 1), "from_deg": round(dom_from), "from_compass": compass(dom_from), "toward_compass": compass(dom_from + 180),
                     "hours": n, "typed": w["typed"], "series": [{"h": h, "speed": round(w["WS"][h], 1), "from": round(w["WD"][h])} for h in range(0, n, 6)]},
            "weather": {"favourable_hours": sum(1 for f in fav_hours if f >= 0.6), "of": n, "assumed_perfect": favourable, "mean_t": round(sum(w["T"]) / n, 1), "mean_rh": round(sum(w["RH"]) / n)},
            "parcels": rows, "summary": {"red": sum(1 for r in rows if r["level"] == "red"), "amber": sum(1 for r in rows if r["level"] == "amber"), "watch": sum(1 for r in rows if r["level"] == "watch"),
                                         "top": [r["parcel_id"] for r in rows if r["risk"] >= THRESHOLD][:6]},
            "verification": ver, "threshold": THRESHOLD, "horizon_hours": n, "notes": w["notes"],
            "data_quality": ["Parcel positions, crops, growth stages and recorded issues in this demo village are DUMMY data (illustrative).",
                             "Wind and weather: " + w["source"] + ".", "The risk index is a transparent scenario model with editable assumptions, not a validated forecast."],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def verify_geometry(source_pid: str, rows: list[dict], ps: dict, w: dict, d: dict) -> dict:
    """Deterministic check, not a language model: recompute distance and bearing a second way, and confirm every flagged parcel is within spore reach and
    either downwind at some hour or close enough that wind direction hardly matters."""
    s = ps[source_pid]["location"]
    failed, checked = [], 0
    for r in rows:
        if r["risk"] < THRESHOLD:
            continue
        checked += 1
        t = ps[r["parcel_id"]]["location"]
        d2, b2 = flat_distance_bearing(s["lat"], s["lon"], t["lat"], t["lon"])
        problems = []
        if abs(d2 - r["distance_m"]) > max(5, 0.02 * r["distance_m"]):
            problems.append(f"distance differs ({r['distance_m']} m vs {round(d2)} m)")
        if angle_diff(b2, r["bearing_deg"]) > 3:
            problems.append(f"bearing differs ({r['bearing_deg']} vs {round(b2)})")
        if r["distance_m"] > d["max_m"]:
            problems.append("outside the spore reach")
        downwind_some = any(angle_diff(r["bearing_deg"], (w["WD"][h] + 180) % 360) <= 75 for h in range(len(w["WD"])))
        if not downwind_some and r["distance_m"] > d["scale_m"] * 0.7:
            problems.append("never downwind and not close")
        if problems:
            failed.append({"parcel_id": r["parcel_id"], "problems": problems})
    return {"passed": not failed, "checked": checked, "failed": failed,
            "method": "distance and bearing recomputed with a second formula (flat-earth east/north metres) and compared; downwind test repeated hour by hour; spore-reach limit enforced"}


def village_exposure() -> dict[str, dict]:
    """For every parcel, the strongest spread risk it faces from ANY infected parcel in the village, under the live forecast: {parcel_id: {risk, source, hours}}."""
    out: dict[str, dict] = {}
    for s in infected_sources(60):
        try:
            r = forecast(s["parcel_id"])
        except Exception:  # noqa: BLE001
            continue
        for x in r["parcels"]:
            if x["risk"] > out.get(x["parcel_id"], {}).get("risk", 0):
                out[x["parcel_id"]] = {"risk": x["risk"], "source": s["parcel_id"], "disease": s["issue"], "hours": x["hours_to_threshold"], "distance_m": x["distance_m"]}
    return out


_PREVENT_WORDS = {"rice_blast": r"blast", "groundnut_rust": r"rust", "banana_sigatoka": r"sigatoka|leaf spot", "cane_rust": r"rust", "banana_cordana": r"cordana|leaf spot"}
_CULTURAL = {
    "rice_blast": ["Inspect leaves of nearby rice every day for spindle-shaped spots with grey centres.", "Avoid extra nitrogen and keep the field free of weeds and old infected stubble.",
                   "Drain standing water where you can and avoid dense, over-watered nurseries.", "Ask your agriculture officer or KVK about a preventive spray for your variety and stage before the weather window opens."],
    "groundnut_rust": ["Check older, lower leaves for orange-brown pustules every day.", "Remove infected plant debris and weeds; avoid planting groundnut after groundnut.", "Ask your agriculture officer or KVK about protectant sprays before spraying anything."],
    "banana_sigatoka": ["Remove and destroy badly spotted leaves; keep the field free of weeds and suckers.", "Improve drainage so leaves dry; avoid waterlogging.", "Ask your agriculture officer or KVK about the spray schedule for your stage."],
    "banana_cordana": ["Remove and destroy badly spotted leaves; keep the field free of weeds and suckers.", "Improve drainage and spacing so leaves dry quickly; avoid waterlogging.",
                       "Ask your agriculture officer or KVK which preventive step is recommended for Cordana; Cropsy's TNAU base has no Cordana management entry."],
    "cane_rust": ["Look for brown-orange pustules on the leaf underside every day.", "Remove badly infected leaves and keep the field clean of weeds.", "Ask your agriculture officer or KVK about protectant sprays before spraying anything."],
}


def prevention(code: str) -> dict:
    """What to do about it: plain cultural steps, plus verbatim TNAU passages (with page) that mention the disease. Doses appear only as quoted from the source."""
    import re
    from app.steps import guides_extra as gx
    d = DISEASES[code]
    rx = re.compile(_PREVENT_WORDS[code], re.I)
    cs = [c for c in gx._chunks() if c["crop"] == d["crop"] and rx.search(c["text"]) and "disease" in (c.get("topics") or [])[:3]]
    cs.sort(key=lambda c: (0 if c.get("source_quality") == "A" else 1, -min(len(c["text"]), 700)))
    seen, ex = set(), []
    for c in cs:
        k = c["text"][:60]
        if k not in seen:
            seen.add(k)
            ex.append(gx._quote(c))
        if len(ex) == 3:
            break
    return {"disease": d["label"], "crop": d["crop"], "steps": _CULTURAL[code], "tnau_passages": ex,
            "note": "The steps are general good practice. Any dose or product appears only as printed in the TNAU passage; check that it is currently registered and ask your KVK before spraying.",
            "ask": f"How to control {d['label'].lower()} in {d['crop'].lower()}?"}


def infected_sources(limit: int = 6) -> list[dict]:
    """Parcels whose recorded problem is a wind-borne disease, most severe first (dummy records)."""
    tools._load_parcels()
    order = {"severe": 0, "moderate": 1, "mild": 2}
    out = []
    for p in tools._PARCELS:
        iss = p.get("observed_issue") or {}
        if iss.get("code") in AIRBORNE and iss.get("severity") in order:
            out.append({"parcel_id": p["parcel_id"], "crop": p["crop"]["name"], "issue": iss.get("label"), "severity": iss.get("severity"), "code": iss["code"]})
    out.sort(key=lambda r: (order[r["severity"]], r["parcel_id"]))
    return out[:limit]
