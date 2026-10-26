"""compare_api.py: 'informed versus uninformed'. Runs the farmer's question through ONE plain model call (no tools, no TNAU passages, no checks) so the
difference to the full Cropsy answer can be seen side by side. On demand only, one small call each, with a per-run cap to keep AWS use low."""
from __future__ import annotations

import os
import threading
import time

from fastapi import APIRouter, HTTPException

from app import config
from app.models import bedrock

router = APIRouter()
_lock = threading.Lock()
_used = {"n": 0}
CAP = int(os.getenv("CROPSY_COMPARE_MAX", "40"))      # calls per server run
SYSTEM = "You are a helpful assistant. Answer the farmer's question briefly in the language it was asked."


@router.post("/api/baseline")
def baseline(payload: dict):
    q = str(payload.get("query", "")).strip()[:600]
    if len(q) < 3:
        raise HTTPException(status_code=422, detail="query required")
    with _lock:
        if _used["n"] >= CAP:
            raise HTTPException(status_code=429, detail=f"Comparison limit reached ({CAP} per run) to protect AWS credit")
        _used["n"] += 1
    t0 = time.perf_counter()
    try:
        text, tokens, _ = bedrock.invoke_text(config.MODEL_MINISTRAL_8B, q, system=SYSTEM, max_tokens=350)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Model call failed: {str(e)[:120]}")
    return {"answer": text.strip(), "model": "Ministral 8B", "cost_usd": bedrock.est_cost(config.MODEL_MINISTRAL_8B, tokens), "latency_ms": round((time.perf_counter() - t0) * 1000),
            "uses": "the model alone: no tools, no TNAU passages, no parcel data, no checks, no sources", "remaining": CAP - _used["n"]}
