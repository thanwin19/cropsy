"""regret_api.py: endpoints for the counterfactual regret engine. The reconstruction and the scan are arithmetic; only the optional intervention brief uses a model (on request, capped)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time

from fastapi import APIRouter, HTTPException

from app import config, regret
from app.models import bedrock

router = APIRouter()
_lock = threading.Lock()
_used = {"n": 0}
_briefs: dict[str, dict] = {}
CAP = int(os.getenv("CROPSY_BRIEF_MAX", "20"))


def _args(p: dict) -> dict:
    def num(k):
        v = p.get(k)
        return None if v in (None, "") else float(v)
    return {"disease_code": p.get("disease_code") or None, "tlo": num("t_low"), "thi": num("t_high"), "rh_min": num("rh_min"), "min_hours": (int(p["min_hours"]) if p.get("min_hours") not in (None, "") else None),
            "latency_min": num("latency_min"), "latency_max": num("latency_max")}


@router.post("/api/regret")
def run(payload: dict):
    pid = str(payload.get("source_parcel", "")).strip().upper()
    try:
        return regret.analyse(pid, **_args(payload))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"analysis failed: {str(e)[:120]}")


def template(res: dict) -> dict:
    s = res["source"]
    risky = [t for t in res["twins"] if t["act"] != "MONITOR"][:8]
    ids = ", ".join(f"{t['parcel_id']}" for t in risky) or "none at present"
    opens = res["now"]["hours_to_open"]
    when = "the weather window is open now" if res["now"]["in_window"] else (f"the next suitable weather window opens in about {opens} hours" if opens is not None else "no suitable weather window is forecast in the next 72 hours")
    en = (f"Early-warning notice (illustrative, dummy data): {s['disease']} was recorded on parcel {s['parcel_id']}. For {s['crop'].lower()} parcels, {when}. Parcels to watch first: {ids}. "
          "Farmers: inspect leaves today, avoid extra nitrogen and standing water, and ask your agriculture officer or KVK which preventive step is recommended for your crop before any spray.")
    ta = (f"முன்னெச்சரிக்கை (மாதிரி தரவு): வயல் {s['parcel_id']}-ல் {s['disease']} பதிவாகியுள்ளது. அடுத்த சில மணி நேரங்களில் நோய்க்கு ஏற்ற வானிலை உருவாகும் வாய்ப்பு உள்ளது. கவனிக்க வேண்டிய வயல்கள்: {ids}. "
          "இன்றே இலைகளைப் பரிசோதிக்கவும்; அதிக தழைச்சத்து உரம், நீர் தேக்கத்தைத் தவிர்க்கவும்; மருந்து தெளிக்கும் முன் உங்கள் வேளாண் அலுவலர் அல்லது KVK-வின் ஆலோசனையைப் பெறவும்.")
    return {"english": en, "tamil": ta}


@router.post("/api/regret/brief")
def brief(payload: dict):
    pid = str(payload.get("source_parcel", "")).strip().upper()
    try:
        res = regret.analyse(pid, **_args(payload))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not res.get("available"):
        raise HTTPException(status_code=409, detail=res["message"])
    base = template(res)
    risky = [t for t in res["twins"] if t["act"] != "MONITOR"][:8]
    key = hashlib.sha1(json.dumps([pid, _args(payload), [(t["parcel_id"], t["act"]) for t in risky]], sort_keys=True, default=str).encode()).hexdigest()
    if key in _briefs:
        return {**_briefs[key], "cached": True}
    if not risky:
        return {**base, "model": "fixed wording (no parcel needs action)", "cost_usd": 0.0, "latency_ms": 0, "cached": False}
    with _lock:
        if _used["n"] >= CAP:
            return {**base, "model": f"fixed wording (brief limit {CAP} per run reached, to protect AWS credit)", "cost_usd": 0.0, "latency_ms": 0, "cached": False}
        _used["n"] += 1
    best = res["reconstruction"]["best"]
    facts = {"disease": res["source"]["disease"], "source_parcel": pid, "likely_infection_window": ({"start": best["start"], "hours": best["hours"], "mean_temp_c": best["mean_t"], "mean_humidity_pct": best["mean_rh"]} if best else None),
             "weather_window_now": res["now"], "parcels_to_act": [{"parcel": t["parcel_id"], "stage": t["stage"], "action": t["act"], "hours_to_open": t["hours_to_open"]} for t in risky]}
    system = ("You write a short early-warning notice for farmers in Tamil Nadu from the FACTS. Use only the facts. Do not invent numbers, costs, chemicals or doses; do not name any pesticide. "
              "Say it is an estimate from dummy demo data. Tell farmers of the listed parcels to inspect leaves today, avoid extra nitrogen and standing water, and ask their agriculture officer or KVK about "
              "preventive action. Return JSON only: {\"tamil\": \"...\", \"english\": \"...\"}; each under 90 words.")
    t0 = time.perf_counter()
    try:
        text, tokens, _ = bedrock.invoke_text(config.MODEL_MINISTRAL_8B, json.dumps(facts, ensure_ascii=False), system=system, max_tokens=600)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(m.group()) if m else {}
        out = {"tamil": str(data.get("tamil") or base["tamil"]), "english": str(data.get("english") or base["english"]), "model": "Ministral 8B", "cost_usd": bedrock.est_cost(config.MODEL_MINISTRAL_8B, tokens),
               "latency_ms": round((time.perf_counter() - t0) * 1000), "cached": False, "note": "The Tamil text is machine-written and has not been checked by a native speaker."}
    except Exception as e:  # noqa: BLE001
        out = {**base, "model": f"fixed wording (model unavailable: {str(e)[:60]})", "cost_usd": 0.0, "latency_ms": 0, "cached": False}
    _briefs[key] = out
    return out
