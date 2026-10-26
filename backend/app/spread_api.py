"""spread_api.py: endpoints for the village spread-risk model. The scan is plain arithmetic (free, instant); only the village alert text uses a model, on request, capped."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time

from fastapi import APIRouter, HTTPException

from app import config, spread
from app.models import bedrock

router = APIRouter()
_lock = threading.Lock()
_used = {"n": 0}
_alerts: dict[str, dict] = {}
CAP = int(os.getenv("CROPSY_ALERT_MAX", "20"))      # alert texts per server run, to protect AWS credit

TA_DISEASE = {"rice_blast": "குலை நோய்", "groundnut_rust": "நிலக்கடலை துரு நோய்", "banana_sigatoka": "வாழை இலைப்புள்ளி (சிகடோகா) நோய்", "cane_rust": "கரும்பு துரு நோய்", "banana_cordana": "வாழை கார்டானா இலைப்புள்ளி நோய்"}


def _args(p: dict) -> dict:
    def num(k):
        v = p.get(k)
        return None if v in (None, "") else float(v)
    return {"disease_code": p.get("disease_code") or None, "wind_speed_kmh": num("wind_speed_kmh"), "wind_from_deg": num("wind_from_deg"), "favourable": bool(p.get("favourable"))}


@router.get("/api/spread/sources")
def sources():
    """Parcels with a recorded wind-borne disease, with how many susceptible neighbours each has within spore reach (a bigger number makes a clearer scan)."""
    out = []
    for s in spread.infected_sources(40):
        try:
            r = spread.forecast(s["parcel_id"])
            n = sum(1 for x in r["parcels"] if x["crop"] == s["crop"] and x["distance_m"] <= r["disease"]["max_m"])
        except Exception:  # noqa: BLE001
            n = 0
        out.append({**s, "neighbours_in_reach": n})
    out.sort(key=lambda r: (-r["neighbours_in_reach"], r["parcel_id"]))
    return {"items": out}


@router.get("/api/spread/prevention")
def prevention(disease_code: str):
    if disease_code not in spread.DISEASES:
        raise HTTPException(status_code=422, detail="unknown disease code")
    return spread.prevention(disease_code)


@router.post("/api/spread")
def scan(payload: dict):
    pid = str(payload.get("source_parcel", "")).strip().upper()
    try:
        return spread.forecast(pid, **_args(payload))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"scan failed: {str(e)[:120]}")


def template(res: dict) -> dict:
    """Plain, fixed-wording alert used when no model is available. Same facts as the model version, no invention."""
    s = res["source"]
    risky = [r for r in res["parcels"] if r["risk"] >= spread.THRESHOLD][:6]
    ids = ", ".join(f"{r['parcel_id']} (about {r['hours_to_threshold']} h)" for r in risky) or "none at present"
    en = (f"Village notice (illustrative, dummy data): {s['disease']} is recorded on parcel {s['parcel_id']}. With the wind from the {res['wind']['from_compass']} and the forecast weather, "
          f"parcels at higher risk of spore exposure within {res['horizon_hours']} hours: {ids}. Farmers of those parcels: check leaves today and again every day, avoid extra nitrogen and standing water, "
          "and ask your agriculture officer or KVK which preventive spray is recommended for your crop before spraying anything.")
    ta_ids = ", ".join(r["parcel_id"] for r in risky) or "இல்லை"
    ta = (f"கிராம அறிவிப்பு (மாதிரி தரவு): வயல் {s['parcel_id']}-ல் {TA_DISEASE.get(s['disease_code'], s['disease'])} பதிவாகியுள்ளது. காற்று {res['wind']['from_compass']} திசையிலிருந்து வீசுகிறது. "
          f"அடுத்த {res['horizon_hours']} மணி நேரத்தில் பாதிப்பு அபாயம் அதிகமுள்ள வயல்கள்: {ta_ids}. இந்த வயல்களின் விவசாயிகள் இன்றே இலைகளைப் பரிசோதிக்கவும்; "
          "அதிக தழைச்சத்து உரம், நீர் தேக்கத்தைத் தவிர்க்கவும்; எந்த மருந்தும் தெளிக்கும் முன் உங்கள் வேளாண் அலுவலர் அல்லது KVK-வின் ஆலோசனையைப் பெறவும்.")
    return {"english": en, "tamil": ta}


@router.post("/api/spread/alert")
def alert(payload: dict):
    pid = str(payload.get("source_parcel", "")).strip().upper()
    try:
        res = spread.forecast(pid, **_args(payload))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    key = hashlib.sha1(json.dumps([pid, payload.get("disease_code"), payload.get("wind_speed_kmh"), payload.get("wind_from_deg"), payload.get("favourable"),
                                   [(r["parcel_id"], r["level"]) for r in res["parcels"] if r["risk"] >= spread.THRESHOLD]], sort_keys=True).encode()).hexdigest()
    if key in _alerts:
        return {**_alerts[key], "cached": True}
    base = template(res)
    risky = [r for r in res["parcels"] if r["risk"] >= spread.THRESHOLD][:6]
    if not risky:
        return {**base, "model": "fixed wording (nothing above the threshold)", "cost_usd": 0.0, "latency_ms": 0, "cached": False}
    with _lock:
        if _used["n"] >= CAP:
            return {**base, "model": f"fixed wording (alert limit {CAP} per run reached, to protect AWS credit)", "cost_usd": 0.0, "latency_ms": 0, "cached": False}
        _used["n"] += 1
    facts = {"source_parcel": pid, "disease": res["source"]["disease"], "wind_from": res["wind"]["from_compass"], "mean_wind_kmh": res["wind"]["mean_speed_kmh"], "hours": res["horizon_hours"],
             "at_risk": [{"parcel": r["parcel_id"], "distance_m": r["distance_m"], "direction": r["bearing_compass"], "risk": r["risk"], "hours_to_threshold": r["hours_to_threshold"]} for r in risky]}
    system = ("You write a short village notice for farmers in Tamil Nadu from the FACTS given. Use only the facts. Do not invent numbers, chemicals or doses; do not name any pesticide. "
              "Say it is an early-warning estimate from dummy demo data. Tell farmers of the listed parcels to inspect leaves today, avoid extra nitrogen and standing water, and ask their agriculture officer or KVK "
              "about preventive action. Return JSON only: {\"tamil\": \"...\", \"english\": \"...\"}; each under 90 words.")
    t0 = time.perf_counter()
    try:
        text, tokens, _ = bedrock.invoke_text(config.MODEL_MINISTRAL_8B, json.dumps(facts, ensure_ascii=False), system=system, max_tokens=600)
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(m.group()) if m else {}
        out = {"tamil": str(data.get("tamil") or base["tamil"]), "english": str(data.get("english") or base["english"]), "model": "Ministral 8B",
               "cost_usd": bedrock.est_cost(config.MODEL_MINISTRAL_8B, tokens), "latency_ms": round((time.perf_counter() - t0) * 1000), "cached": False,
               "note": "The Tamil text is machine-written and has not been checked by a native speaker."}
    except Exception as e:  # noqa: BLE001
        out = {**base, "model": f"fixed wording (model unavailable: {str(e)[:60]})", "cost_usd": 0.0, "latency_ms": 0, "cached": False}
    _alerts[key] = out
    return out
