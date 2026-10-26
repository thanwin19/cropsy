"""
tools.py — Step 4: Parcel lookup, weather (live Open-Meteo → fallback CSV),
           village query, crop stage calendar.
"""
from __future__ import annotations

import csv
import json
import logging
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from app import config
from app.schemas import PipelineState, TraceEntry

log = logging.getLogger(__name__)

# ── Parcel data (loaded once) ─────────────────────────────────────────────────
_PARCELS: list[dict] = []
_PARCEL_BY_ID: dict[str, dict] = {}
_PARCEL_BY_SURVEY: dict[str, dict] = {}


def _load_parcels():
    global _PARCELS, _PARCEL_BY_ID, _PARCEL_BY_SURVEY
    if _PARCELS:
        return
    if not config.PARCELS_FILE.exists():
        log.warning("parcels.json not found at %s", config.PARCELS_FILE)
        return
    with open(config.PARCELS_FILE, encoding="utf-8") as f:
        _PARCELS = json.load(f)
    for p in _PARCELS:
        pid = p.get("parcel_id") or p.get("survey_no", "")
        _PARCEL_BY_ID[pid] = p
        sno = str(p.get("survey_no", ""))
        _PARCEL_BY_SURVEY[sno] = p


def parcel_from_text(text: str) -> str | None:
    """'tm 45', 'TM-045', 'tm-7' in the farmer's words -> that parcel's id if it exists (the web app does the same before it calls the API)."""
    import re as _re
    m = _re.search(r"\bTM[-\s]?0*(\d{1,3})\b", text or "", _re.IGNORECASE)
    if not m:
        return None
    _load_parcels()
    n = int(m.group(1))
    pid = f"TM-{n:02d}"
    return pid if pid in _PARCEL_BY_ID else None


# ── Weather cache (loaded once) ───────────────────────────────────────────────
_WEATHER_CACHE: dict[str, list[dict]] = {}   # parcel_id -> rows


def _load_weather():
    global _WEATHER_CACHE
    if _WEATHER_CACHE:
        return
    f = config.WEATHER_FILE
    if not f.exists():
        log.warning("weather/daily.csv not found")
        return
    with open(f, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pid = row.get("parcel_id", "")
            _WEATHER_CACHE.setdefault(pid, []).append(row)


# ── Parcel lookup ─────────────────────────────────────────────────────────────
def parcel_lookup(state: PipelineState) -> PipelineState:
    _load_parcels()
    t0 = time.perf_counter()

    parcel = None
    if state.parcel_id:
        parcel = _PARCEL_BY_ID.get(state.parcel_id) or _PARCEL_BY_SURVEY.get(state.parcel_id)

    if parcel is None and state.parcel_id:
        # Fuzzy: try prefix match
        prefix = state.parcel_id.upper()
        for pid, p in _PARCEL_BY_ID.items():
            if pid.upper().startswith(prefix):
                parcel = p
                break

    latency_ms = (time.perf_counter() - t0) * 1000
    if parcel:
        state.parcel_context = parcel
        status = "ok"
        summary = f"found parcel {parcel.get('parcel_id')} crop={parcel.get('crop', {}).get('name')}"
    else:
        status = "not_found"
        summary = f"parcel_id={state.parcel_id} not found in {len(_PARCELS)} parcels"
        log.info("parcel_lookup: %s", summary)

    state.trace.append(TraceEntry(
        step="tools/parcel_lookup", tool_or_model="parcel_lookup",
        why="Load parcel soil/crop/management context",
        status=status, latency_ms=latency_ms, est_cost_usd=0.0,
        input_summary=f"parcel_id={state.parcel_id}",
        output_summary=summary,
    ))
    return state


# ── Stage calendar ────────────────────────────────────────────────────────────
def stage_calendar(state: PipelineState) -> PipelineState:
    t0 = time.perf_counter()
    p = state.parcel_context or {}
    crop_info = p.get("crop", {}) or {}
    stage = crop_info.get("stage", "Unknown")
    dap = crop_info.get("days_after_planting", "Unknown")
    summary = f"stage={stage} dap={dap}"
    latency_ms = (time.perf_counter() - t0) * 1000
    state.trace.append(TraceEntry(
        step="tools/stage_calendar", tool_or_model="stage_calendar",
        why="Confirm crop stage from parcel record",
        status="ok", latency_ms=latency_ms, est_cost_usd=0.0,
        input_summary=f"crop={crop_info.get('name')}",
        output_summary=summary,
    ))
    return state


# ── Satellite crop-health signal (real Sentinel-2 NDVI, precomputed offline) ──────────────────
_SAT: dict = {}


def _load_satellite() -> dict:
    global _SAT
    if _SAT:
        return _SAT
    f = config.SATELLITE_SUMMARY_FILE
    if f.exists():
        _SAT = json.loads(f.read_text(encoding="utf-8"))
    return _SAT


def satellite(state: PipelineState) -> PipelineState:
    """Attach the parcel's satellite vegetation signal. The data is real (Sentinel-2 L2A at the parcel's coordinates);
    the crop labels around it are dummy, which the answer must say."""
    t0 = time.perf_counter()
    sat = _load_satellite()
    pid = (state.parcel_context or {}).get("parcel_id") or state.parcel_id
    entry = (sat.get("parcels") or {}).get(pid) if sat else None
    if entry:
        state.satellite = {**entry, "as_of": sat.get("as_of"), "source": sat.get("source")}
    try:                                                  # one structure with every value, its basis and date (latest scene vs monthly composite vs baseline)
        from app import field_analysis
        canon = field_analysis.canonical(pid) if pid else None
        if canon:
            state.satellite = {**(state.satellite or {}), "canonical": canon, "as_of": canon.get("as_of")}
    except Exception as e:  # noqa: BLE001
        log.warning("canonical satellite evidence unavailable: %s", e)
    state.trace.append(TraceEntry(
        step="tools/satellite", tool_or_model="sentinel2_ndvi_cache",
        why="Satellite vegetation trend gives an early, objective crop-stress signal before symptoms are visible",
        status="ok" if entry else "skipped", latency_ms=(time.perf_counter() - t0) * 1000, est_cost_usd=0.0,
        input_summary=f"parcel={pid}",
        output_summary=(f"NDVI {entry.get('latest_ndvi')} on {entry.get('latest_date')}, change {entry.get('change')}, "
                        f"status={entry.get('status')}") if entry else "no satellite summary available for this parcel"))
    return state


# ── Village query ─────────────────────────────────────────────────────────────
def village_query(state: PipelineState) -> PipelineState:
    _load_parcels()
    t0 = time.perf_counter()

    q = (state.normalized_query or state.query).lower()
    # Detect crop filter
    crop_filter = None
    for crop in [c.lower() for c in config.CROPS]:
        if crop in q or any(a in q and v == crop for a, v in config.CROP_ALIASES.items()):
            crop_filter = crop
            break

    results: list[dict] = []
    for p in _PARCELS:
        crop_name = (p.get("crop", {}) or {}).get("name", "").lower()
        if crop_filter and crop_filter not in crop_name:
            continue
        results.append({
            "parcel_id": p.get("parcel_id"),
            "crop": (p.get("crop", {}) or {}).get("name"),
            "area_ha": p.get("area_ha"),
        })

    total_area = round(sum(r["area_ha"] or 0 for r in results), 2)

    # Store in parcel_context as village summary
    state.parcel_context = state.parcel_context or {}
    state.parcel_context["village_summary"] = {
        "crop_filter": crop_filter,
        "count": len(results),
        "total_area_ha": total_area,
        "parcels": results[:10],  # top 10 for context
    }

    latency_ms = (time.perf_counter() - t0) * 1000
    state.trace.append(TraceEntry(
        step="tools/village_query", tool_or_model="village_query",
        why="Aggregate village-level crop/area stats",
        status="ok", latency_ms=latency_ms, est_cost_usd=0.0,
        input_summary=f"crop_filter={crop_filter}",
        output_summary=f"count={len(results)} total_area={total_area}ha",
    ))
    return state


# ── Weather ───────────────────────────────────────────────────────────────────
def weather(state: PipelineState) -> PipelineState:
    _load_weather()
    t0 = time.perf_counter()

    p = state.parcel_context or {}
    loc = p.get("location", {}) or {}
    lat = loc.get("lat")
    lon = loc.get("lon")

    # Honour failure injection
    force_timeout = (state.inject_failure == "open_meteo_timeout")

    live_ok = False
    if lat and lon and not force_timeout:
        try:
            r = requests.get(
                config.OPEN_METEO_URL,
                params={
                    "latitude": lat, "longitude": lon,
                    "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
                    "forecast_days": 7,
                    "timezone": "Asia/Kolkata",
                },
                timeout=config.OPEN_METEO_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            daily = data.get("daily", {})
            forecast = [
                {
                    "date": daily["time"][i],
                    "rain_mm": daily["precipitation_sum"][i],
                    "tmax_c": daily["temperature_2m_max"][i],
                    "tmin_c": daily["temperature_2m_min"][i],
                    "source": "Open-Meteo live",
                }
                for i in range(len(daily.get("time", [])))
            ]
            state.weather_data = {"forecast": forecast[:7]}
            state.weather_source = "live"
            live_ok = True
        except Exception as e:
            log.warning("Open-Meteo failed: %s — falling back to CSV", e)

    if not live_ok:
        pid = state.parcel_id or ""
        rows = _WEATHER_CACHE.get(pid, [])
        # Return next 3 forecast rows
        today_str = str(date.today())
        forecast_rows = [
            r for r in rows
            if r.get("type") == "forecast" and r.get("date", "") >= today_str
        ][:7]
        if not forecast_rows:
            forecast_rows = rows[-7:] if rows else []

        state.weather_data = {
            "forecast": [
                {
                    "date": r.get("date"),
                    "rain_mm": r.get("rain_mm") or r.get("precipitation_mm"),
                    "tmax_c": r.get("tmax_c") or r.get("temperature_max_c"),
                    "tmin_c": r.get("tmin_c") or r.get("temperature_min_c"),
                    "source": "cached CSV (dummy)",
                }
                for r in forecast_rows
            ]
        }
        state.weather_source = "cached"

    latency_ms = (time.perf_counter() - t0) * 1000
    forecast_days = len((state.weather_data or {}).get("forecast", []))
    state.trace.append(TraceEntry(
        step="tools/weather", tool_or_model="open_meteo" if live_ok else "csv_cache",
        why="Get weather forecast for parcel location",
        status="ok", latency_ms=latency_ms, est_cost_usd=0.0,
        input_summary=f"lat={lat} lon={lon} inject={state.inject_failure}",
        output_summary=f"source={state.weather_source} days={forecast_days}",
    ))
    return state


# ── Dispatcher: run tools based on route/intent ───────────────────────────────
def run(state: PipelineState) -> PipelineState:
    intent = state.intent or "general"
    route = state.route or config.ROUTE_ADVISORY

    # Always look up parcel if parcel_id given
    if state.parcel_id:
        state = parcel_lookup(state)

    if intent == "growth_stage":
        state = stage_calendar(state)

    # Weather is needed for any weather question AND for operational decisions that depend on it
    # (spray / irrigate / fertilize / "rain is forecast"), otherwise the answer would repeat the user's own claim.
    qtxt = f"{state.query} {state.normalized_query or ''}".lower()
    needs_weather = intent == "weather" or bool(re.search(
        r"weather|rain|forecast|mazhai|storm|shower|drizzle|spray|irrigat|fertili[sz]|waterlog|drain|மழை|உரம்", qtxt))
    if needs_weather and state.parcel_context:
        state = weather(state)

    if state.parcel_context and re.search(
        r"health|healthy|stress|ndvi|savi|evi|ndre|ndmi|ndwi|vegetation|satellite|vigou?r|greenness|monitor|how is|how are|doing|wilt|yellow|canopy|growth|poor|part of my|"
        r"which (area|part|corner|side)|where|inspect|decreas|dropp|falling|declin|baseline|compare|trend|ஆரோக்கிய|பசுமை|நலம்|செயற்கைக்கோள்|irukka|nalama|"
        r"disease|pest|blast|blight|rot|spot|what is wrong|problem|risk", qtxt):
        state = satellite(state)

    if intent == "village_query" or route == config.ROUTE_ROUTINE:
        q = (state.normalized_query or state.query).lower()
        if any(w in q for w in ["how many", "count", "total", "all parcels", "village"]):
            state = village_query(state)

    return state
