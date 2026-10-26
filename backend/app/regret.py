"""
regret.py: "Counterfactual regret" for wind-borne crop diseases: when did this infection most likely become possible, and who is in the same position now?

BACKWARD  For a parcel with a recorded disease, scan the last 3 weeks of hourly weather for runs of hours that suit the disease (temperature and
          humidity both inside its window for long enough). Windows that ended just before the likely infection date (symptom date minus an assumed
          latency range) are the candidate "missed prevention moments". A window must also fall after the crop was planted.
ECONOMICS The potential loss is area x the parcel's own yield history x price x an editable loss share; regret is that loss minus the cost of
          prevention. Only inputs the farmer can edit: nothing is guessed silently, and the prevention cost is left for the farmer to enter.
FORWARD   Look at the next 72 hours of forecast for the same kind of window, and list every parcel of the same crop with a three-part check
          (temperature, humidity, crop stage) that decides ACT NOW, PREPARE or MONITOR.

HONEST LIMITS (shown in the app): the disease weather windows, minimum run length and latency ranges are model assumptions, not TNAU figures; TNAU's pages give
only the qualitative link between moist weather and these diseases. The weather history is a model analysis for one point, not a field sensor, so the
weather part is the same for every parcel and parcels differ only by crop stage. A "candidate window" is a plausible explanation, never proof.
Parcel records, planting dates and recorded issues are dummy demo data.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import requests

from app import config, spread
from app.steps import tools

LATENCY = {"rice_blast": (4, 10), "groundnut_rust": (7, 14), "banana_sigatoka": (14, 35), "cane_rust": (7, 14)}      # days from infection to visible symptoms (assumption)
MIN_HOURS = {"rice_blast": 10, "groundnut_rust": 8, "banana_sigatoka": 12, "cane_rust": 8}                              # consecutive favourable hours (assumption)
LOSS_BY_SEVERITY = {"mild": 5, "moderate": 15, "severe": 30}                                                          # % of yield at risk, scenario default (assumption, editable)
PAST_DAYS = 21
_cache: dict = {}


def _series(lat: float, lon: float) -> dict | None:
    key = (round(lat, 2), round(lon, 2))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 900:
        return hit[1]
    try:
        r = requests.get(config.OPEN_METEO_URL, params={"latitude": lat, "longitude": lon, "past_days": PAST_DAYS, "forecast_days": 4, "timezone": "Asia/Kolkata",
                                                         "hourly": "temperature_2m,relative_humidity_2m"}, timeout=8)
        r.raise_for_status()
        h = r.json()["hourly"]
        out = {"time": h["time"], "T": h["temperature_2m"], "RH": h["relative_humidity_2m"]}
        if len(out["time"]) < 48 or any(v is None for v in out["T"][:48]):
            return None
        _cache[key] = (time.time(), out)
        return out
    except Exception:  # noqa: BLE001
        return None


def _fav(t, rh, tlo, thi, rhmin) -> bool:
    return t is not None and rh is not None and tlo <= t <= thi and rh >= rhmin


def runs(times: list[str], flags: list[bool], min_hours: int) -> list[dict]:
    """Runs of consecutive favourable hours that last at least min_hours: [{start_i, end_i, hours}] (end_i is the last favourable hour)."""
    out, i, n = [], 0, len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j + 1 < n and flags[j + 1]:
                j += 1
            if j - i + 1 >= min_hours:
                out.append({"i": i, "j": j, "hours": j - i + 1})
            i = j + 1
        else:
            i += 1
    return out


def analyse(source_pid: str, disease_code: str | None = None, tlo: float | None = None, thi: float | None = None, rh_min: float | None = None,
            min_hours: int | None = None, latency_min: float | None = None, latency_max: float | None = None) -> dict:
    t0 = time.perf_counter()
    tools._load_parcels()
    ps = {p["parcel_id"]: p for p in tools._PARCELS}
    src = ps.get(source_pid)
    if not src:
        raise ValueError(f"unknown parcel {source_pid}")
    code = disease_code or (src.get("observed_issue") or {}).get("code")
    if code not in spread.AIRBORNE:
        raise ValueError(f"{source_pid}'s recorded problem is not a wind-borne disease this model covers")
    d = spread.AIRBORNE[code]
    lo, hi = (tlo if tlo is not None else d["t"][0]), (thi if thi is not None else d["t"][1])
    rhm = rh_min if rh_min is not None else d["rh_min"]
    mh = int(min_hours if min_hours is not None else MIN_HOURS[code])
    lat_lo, lat_hi = (latency_min if latency_min is not None else LATENCY[code][0]), (latency_max if latency_max is not None else LATENCY[code][1])
    loc = src["location"]
    s = _series(loc["lat"], loc["lon"])
    if not s:
        return {"available": False, "source": {"parcel_id": source_pid, "disease": d["label"]},
                "message": "Past weather could not be fetched, so the infection window cannot be reconstructed. Only the present-day risk view (village spread scan) is available.",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    times = s["time"]
    now_s = datetime.now().strftime("%Y-%m-%dT%H:00")
    now_i = next((i for i, t in enumerate(times) if t >= now_s), len(times) - 1)
    flags = [_fav(s["T"][i], s["RH"][i], lo, hi, rhm) for i in range(len(times))]
    allruns = runs(times, flags, mh)

    def info(r):
        seg = range(r["i"], r["j"] + 1)
        start, end = datetime.fromisoformat(times[r["i"]]), datetime.fromisoformat(times[r["j"]]) + timedelta(hours=1)
        return {"start": times[r["i"]], "end": end.strftime("%Y-%m-%dT%H:00"), "hours": r["hours"], "mean_t": round(sum(s["T"][i] for i in seg) / r["hours"], 1),
                "mean_rh": round(sum(s["RH"][i] for i in seg) / r["hours"]), "hours_ago_at_start": round((datetime.fromisoformat(times[now_i]) - start).total_seconds() / 3600),
                "past": r["j"] < now_i, "now_inside": r["i"] <= now_i <= r["j"]}

    past_runs = [info(r) for r in allruns if r["j"] < now_i + 1 and r["i"] <= now_i]
    future_runs = [info(r) for r in allruns if r["j"] >= now_i]

    # backward: where was the likely infection window?
    iss = src.get("observed_issue") or {}
    since = float(iss.get("since_days") or 0)
    planted = None
    try:
        planted = datetime.fromisoformat(str((src.get("crop") or {}).get("planting_date")) + "T00:00")
    except Exception:  # noqa: BLE001
        pass
    now_dt = datetime.fromisoformat(times[now_i])
    inf_from, inf_to = now_dt - timedelta(days=since + lat_hi), now_dt - timedelta(days=since + lat_lo)
    cands = []
    for r in allruns:
        a, b = datetime.fromisoformat(times[r["i"]]), datetime.fromisoformat(times[r["j"]]) + timedelta(hours=1)
        if b >= inf_from and a <= inf_to and r["j"] < now_i:
            i = info(r)
            i["after_planting"] = planted is None or b > planted
            cands.append(i)
    cands = [c for c in cands if c["after_planting"]]
    cands.sort(key=lambda c: -c["hours"])
    best = cands[0] if cands else None
    recon = {"symptom_noted_days_ago": since, "latency_days": [lat_lo, lat_hi], "expected_infection_from": inf_from.strftime("%Y-%m-%dT%H:00"), "expected_infection_to": inf_to.strftime("%Y-%m-%dT%H:00"),
             "candidates": cands[:4], "best": best, "history_hours": len(times[:now_i + 1])}
    recon["statement"] = (f"The weather suited {d['label'].lower()} for {best['hours']} hours in a row from {best['start'].replace('T', ' ')} ({round(best['hours_ago_at_start'] / 24, 1)} days ago): "
                          f"about {best['mean_t']} C and {best['mean_rh']}% humidity. That is the most plausible infection window, and the moment a preventive step would have mattered. "
                          "It is a plausible explanation, not proof." if best else
                          f"No run of at least {mh} favourable hours fell in the expected infection period ({inf_from.strftime('%d %b')} to {inf_to.strftime('%d %b')}) after planting. "
                          "The infection may have come from a window outside these assumptions, from seed or nearby inoculum, or the thresholds above need adjusting.")

    # economics (inputs the farmer edits; only the parcel's own numbers are filled in)
    from app import advisory_extras as ex
    from app.steps import facts
    yo = None
    try:
        yo = ex.yield_outlook(src)
    except Exception:  # noqa: BLE001
        pass
    area = float(src.get("area_ha") or 0)
    msp = facts._msp(src["crop"]["name"], {"mid": yo["expected_mid"], "unit": yo["unit"], "area_ha": area} if yo else None)
    price = msp["rows"][0]["msp_rs_per_quintal"] if msp.get("has_msp") and msp.get("rows") else None
    sev = iss.get("severity") or "moderate"
    econ = {"area_ha": area, "area_acre": round(area * 2.471, 2), "yield_mid_t_ha": (yo["expected_mid"] if yo and str(yo["unit"]).startswith("t/ha") else None),
            "yield_unit": yo["unit"] if yo else None, "price_per_quintal": price, "price_basis": ("MSP 2024-25" if price else "no MSP in our data: enter your own price"),
            "severity": sev, "default_loss_pct": LOSS_BY_SEVERITY.get(sev, 15),
            "note": "Loss share is a scenario default for the recorded severity, not a measurement: change it. Enter your own cost of prevention; none is assumed."}

    # forward: the same weather window in the next 72 hours, and every parcel of this crop
    nxt = next((r for r in future_runs), None)
    now_in = bool(nxt and nxt["now_inside"])
    hours_to_open = None if not nxt else (0 if now_in else max(0, round((datetime.fromisoformat(nxt["start"]) - now_dt).total_seconds() / 3600)))
    hours_left = None if not nxt else round((datetime.fromisoformat(nxt["end"]) - now_dt).total_seconds() / 3600)
    twins = []
    for pid, p in ps.items():
        if pid == source_pid or (p.get("crop") or {}).get("name") != d["crop"]:
            continue
        stage = str((p["crop"]).get("stage", "")).split(" - ")[0]
        sw = d["stage_weight"].get(stage, 0.6)
        has_window = nxt is not None and hours_to_open is not None and hours_to_open <= 72
        temp_ok = has_window and lo <= nxt["mean_t"] <= hi
        hum_ok = has_window and nxt["mean_rh"] >= rhm
        stage_ok = sw >= 0.5
        if has_window and temp_ok and hum_ok and stage_ok:
            act = "ACT NOW" if hours_to_open <= 24 else "PREPARE"
        else:
            act = "MONITOR"
        why_down = [] if act != "MONITOR" else ([] if has_window and temp_ok and hum_ok and stage_ok else
                                                 [x for x, ok in (("no suitable weather window in the next 72 h", has_window), ("temperature outside the window", temp_ok or not has_window),
                                                                  ("humidity below the threshold", hum_ok or not has_window), (f"crop stage ({stage}) is not very susceptible", stage_ok)) if not ok])
        twins.append({"parcel_id": pid, "stage": stage, "stage_weight": sw, "status": ("in_window" if now_in else "opens" if has_window else "none"), "hours_to_open": hours_to_open if has_window else None,
                      "hours_left": hours_left if now_in else None, "act": act, "checks": {"temperature": bool(temp_ok), "humidity": bool(hum_ok), "stage": bool(stage_ok)}, "downgrade_reason": why_down,
                      "opens_at": nxt["start"] if has_window else None})
    order = {"ACT NOW": 0, "PREPARE": 1, "MONITOR": 2}
    twins.sort(key=lambda t: (order[t["act"]], -t["stage_weight"], t["parcel_id"]))
    verification = {"passed": all(not (t["act"] != "MONITOR" and not all(t["checks"].values())) for t in twins), "checked": sum(1 for t in twins if t["act"] != "MONITOR"),
                    "method": "ACT NOW and PREPARE are allowed only when temperature, humidity and crop stage all pass; any miss is downgraded to MONITOR (plain rules, no model)"}
    return {"available": True, "source": {"parcel_id": source_pid, "crop": src["crop"]["name"], "stage": str(src["crop"].get("stage", "")).split(" - ")[0], "lat": loc["lat"], "lon": loc["lon"],
                                          "disease_code": code, "disease": d["label"], "severity": sev, "planted": (src["crop"].get("planting_date"))},
            "params": {"t_low": lo, "t_high": hi, "rh_min": rhm, "min_hours": mh, "latency_min": lat_lo, "latency_max": lat_hi},
            "evidence": [{"claim": c, "source": s_["title"], "url": s_["url"], "kind": k} for c, s_, k in d["evidence"][:2]] + [
                {"claim": f"Weather window {lo}-{hi} C and humidity at least {rhm}% for {mh}+ hours in a row", "source": "Model assumption", "url": "", "kind": "assumption"},
                {"claim": f"Time from infection to visible symptoms {lat_lo:g}-{lat_hi:g} days", "source": "Model assumption", "url": "", "kind": "assumption"},
                {"claim": f"Potential loss share by severity ({sev}: {econ['default_loss_pct']}%)", "source": "Scenario default", "url": "", "kind": "assumption"}],
            "history": {"start": times[0], "now": times[now_i], "end": times[-1], "hours": len(times), "source": "Open-Meteo hourly model analysis and forecast (not a field sensor)",
                        "series": {"time": times, "T": [round(x, 1) for x in s["T"]], "RH": [round(x) for x in s["RH"]], "fav": [1 if f else 0 for f in flags], "now_i": now_i}},
            "windows_past": past_runs, "windows_next": future_runs[:3], "reconstruction": recon, "economics": econ,
            "now": {"in_window": now_in, "hours_to_open": hours_to_open, "hours_left": hours_left},
            "twins": twins, "summary": {"act_now": sum(1 for t in twins if t["act"] == "ACT NOW"), "prepare": sum(1 for t in twins if t["act"] == "PREPARE"), "monitor": sum(1 for t in twins if t["act"] == "MONITOR")},
            "verification": verification,
            "data_quality": ["Parcel records, planting dates, growth stages and recorded issues are DUMMY demo data.", "Weather: " + "Open-Meteo hourly model analysis for the past and forecast for the next 72 hours (one point for the whole village).",
                             "Windows, run length and latency are editable model assumptions, not TNAU figures. Because the weather is the same for every parcel, parcels differ only by crop and stage."],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
