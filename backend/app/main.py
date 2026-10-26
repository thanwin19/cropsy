"""
main.py — Cropsy FastAPI application.

Endpoints:
  GET  /health
  POST /api/advisory          — main pipeline (Phase7AdvisoryResult)
  POST /api/chat              — simple chat with parcel context
  POST /api/v1/query          — legacy endpoint (maps to advisory)
  POST /api/v1/upload         — file upload (image / document)
  GET  /api/v1/executions     — list execution records
  GET  /api/v1/executions/{id}
  GET  /api/parcels           — list all parcels
  GET  /api/parcels/{id}      — single parcel
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app import pipeline
from app.schemas import (
    AdvisoryRequest,
    ChatRequest,
    ChatResponse,
    Phase7AdvisoryResult,
    UploadRequest,
    UploadResponse,
)
from app.store.memory import get_store
from app.steps import tools as _tools  # use module attributes: _load_parcels() rebinds _PARCELS, so never import it by name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(
    title="Cropsy Advisory API",
    description="Multi-model agentic agriculture advisory for Then Malai, Tamil Nadu",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app import corrections_api  # noqa: E402
app.include_router(corrections_api.router)
from app import compare_api  # noqa: E402
app.include_router(compare_api.router)
from app import spread_api  # noqa: E402
app.include_router(spread_api.router)
from app import regret_api  # noqa: E402
app.include_router(regret_api.router)
from app import voice_api  # noqa: E402
app.include_router(voice_api.router)
from app import document_api  # noqa: E402
app.include_router(document_api.router)
from app import stcr_api  # noqa: E402
app.include_router(stcr_api.router)
from app import field_api  # noqa: E402
app.include_router(field_api.router)

# Static image serving
_images_dir = config.DATA_DIR / "images"
if os.environ.get("CROPSY_IMAGE_BUCKET"):
    # Deployed (Lambda has a 250 MB package limit): photos that are not in the package are served from the S3 bucket through a short-lived signed link.
    from fastapi.responses import FileResponse, RedirectResponse

    @app.get("/images/{path:path}", include_in_schema=False)
    def _image_from_bucket(path: str):
        local = (_images_dir / path).resolve()
        if _images_dir.resolve() in local.parents and local.is_file():
            return FileResponse(local)
        if ".." in path:
            raise HTTPException(status_code=404)
        from app import aws_resources
        url = aws_resources.session().client("s3").generate_presigned_url(
            "get_object", Params={"Bucket": os.environ["CROPSY_IMAGE_BUCKET"], "Key": "staging/images/" + path}, ExpiresIn=900)
        return RedirectResponse(url, status_code=302)
if _images_dir.exists() and not os.environ.get("CROPSY_IMAGE_BUCKET"):
    app.mount("/images", StaticFiles(directory=str(_images_dir)), name="images")

# Map layer rasters (satellite composites, DEM, land cover ...) built offline by scripts/build_layers.py
_layers_dir = config.DATA_DIR / "layers"
if _layers_dir.exists():
    app.mount("/layers", StaticFiles(directory=str(_layers_dir)), name="layers")

# Uploads dir
config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
config.CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "cropsy-backend",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chunks_loaded": _chunk_count(),
        "parcels_loaded": _parcel_count(),
    }


def _chunk_count() -> int:
    try:
        from app.steps import retrieve as _retrieve
        _retrieve._load_chunks()
        return len(_retrieve._CHUNKS)
    except Exception:
        return 0


def _parcel_count() -> int:
    _tools._load_parcels()
    return len(_tools._PARCELS)


# ── Advisory ──────────────────────────────────────────────────────────────────
@app.post("/api/advisory", response_model=Phase7AdvisoryResult)
def advisory(req: AdvisoryRequest, x_cropsy_consent: Optional[str] = Header(None)):
    execution_id = f"exec-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    result = pipeline.run(req)
    gs = result.fertilizer_guides or []
    if gs and gs[0].get("id") == "clarify" and gs[0].get("reason") != "greeting" and (x_cropsy_consent or "").lower() == "yes":
        from app import misses
        misses.record(req.query, req.parcel_id, "not understood")

    # Persist
    record = result.model_dump()
    record["execution_id"] = execution_id
    record["created_at"] = created_at
    get_store().save(execution_id, record)

    return result


# ── Media for an answer (separate call, so the text never waits for it) ──
@app.post("/api/media")
def answer_media(payload: dict):
    from app import media
    q = str(payload.get("query") or "")
    plan = media.plan(q, str(payload.get("answer") or ""), payload.get("crop"))
    if plan.get("weather_chart"):
        plan["weather"] = media.weather_series(payload.get("parcel_id")) or None
        plan["weather_chart"] = bool(plan["weather"])
    return plan


# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Simple chat endpoint — wraps advisory pipeline, returns plain reply."""
    adv_req = AdvisoryRequest(query=req.message, parcel_id=req.parcel_id)
    result = pipeline.run(adv_req)
    return ChatResponse(
        reply=result.answer or "Advisory generated.",
        answer=result.answer,
        recommendations=result.recommendations,
        model_used=result.model_selected,
    )


# ── Legacy query endpoint (POST /api/v1/query) ────────────────────────────────
@app.post("/api/v1/query")
def legacy_query(payload: dict):
    """Accepts {query, survey_no, village, image_paths} → Phase7AdvisoryResult."""
    query = payload.get("query", "")
    parcel_id = payload.get("survey_no") or payload.get("parcel_id")
    req = AdvisoryRequest(query=query, parcel_id=parcel_id)
    result = pipeline.run(req)
    return result.model_dump()


# ── Upload ────────────────────────────────────────────────────────────────────
@app.post("/api/v1/upload", response_model=UploadResponse)
def upload_file(payload: UploadRequest):
    """Accept base64 data URL, save to uploads/, return file_path."""
    data_url = payload.data
    if "," in data_url:
        header, b64 = data_url.split(",", 1)
        mime = header.split(":")[1].split(";")[0] if ":" in header else "application/octet-stream"
    else:
        b64 = data_url
        mime = "application/octet-stream"

    ext = mime.split("/")[-1].replace("jpeg", "jpg")
    safe_name = payload.filename.replace(" ", "_")
    dest = config.UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    dest.write_bytes(base64.b64decode(b64))

    return UploadResponse(
        filename=dest.name,
        original_filename=payload.filename,
        file_path=str(dest),
        file_type=mime,
        url=f"/uploads/{dest.name}",
    )


# ── Executions ────────────────────────────────────────────────────────────────
@app.get("/api/privacy")
def privacy_notes():
    """What the prototype collects, in plain words (shown in the app's privacy panel)."""
    return {"collects": [
        "Your question text and the parcel you picked, to answer them.",
        "A photo only if you attach one: it is sent to this server and to AWS Bedrock to be compared with reference photos. Only its file name is kept in the history record.",
        "If you allow it: the text of questions Cropsy could not understand (no name, no phone, no location), to improve the guidance.",
    ], "does_not_collect": ["Your name, phone number or GPS location.", "Contacts, files or anything outside what you type or attach."],
        "kept": "Answer history is held in server memory until the server restarts; chat history is kept in your browser only. Parcel records in this demo are dummy data.",
        "delete": "DELETE /api/my-data clears the saved history, uploaded files and the unclear-questions log."}


@app.delete("/api/my-data")
def delete_my_data():
    """Prototype 'delete my data': clears the server-side history, uploaded files and the unclear-questions log."""
    from app import misses
    get_store().clear()
    removed = 0
    for f in config.UPLOAD_DIR.glob("*"):
        try:
            if f.is_file():
                f.unlink()
                removed += 1
        except OSError:
            pass
    misses.clear()
    return {"cleared": True, "uploads_removed": removed}


@app.post("/api/feedback")
def feedback(payload: dict, x_cropsy_consent: Optional[str] = Header(None)):
    """Thumbs up or down on an answer. Stored only if the farmer agreed to help improve Cropsy; used for the officer review list."""
    if (x_cropsy_consent or "").lower() != "yes":
        return {"saved": False, "reason": "consent not given"}
    from app import misses
    misses.record_feedback({"query": str(payload.get("query", ""))[:300], "parcel_id": payload.get("parcel_id"), "route": payload.get("route"),
                            "helpful": bool(payload.get("helpful")), "confidence": payload.get("confidence"),
                            "answer": str(payload.get("answer", ""))[:1500]})
    return {"saved": True}


@app.get("/api/feedback")
def feedback_list(limit: int = Query(100, ge=1, le=500)):
    from app import misses
    return {"items": list(reversed(misses.feedback_recent(limit)))}


@app.get("/api/offices")
def offices():
    """Nearest KVK and soil testing labs (approximate positions) with straight-line distance from the village."""
    import math
    d = json.loads((config.DATA_DIR / "offices.json").read_text(encoding="utf-8"))
    v = d["village"]
    for o in d["items"]:
        la1, lo1, la2, lo2 = map(math.radians, (v["lat"], v["lon"], o["lat"], o["lon"]))
        a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        o["km_straight_line"] = round(6371 * 2 * math.asin(math.sqrt(a)))
    d["items"].sort(key=lambda o: o["km_straight_line"])
    return d


@app.get("/api/knowledge")
def knowledge():
    from app import knowledge_info
    return knowledge_info.summary()


@app.get("/api/priority")
def priority_list(parcel_id: Optional[str] = None, limit: int = Query(10, ge=1, le=120)):
    from app import priority
    return priority.ranked(parcel_id, limit)


@app.get("/api/misses")
def list_misses(limit: int = Query(100, ge=1, le=500)):
    from app import misses
    return {"items": list(reversed(misses.recent(limit)))}


@app.get("/api/v1/executions")
def list_executions(verification_status: Optional[str] = Query(None)):
    statuses = verification_status.split(",") if verification_status else None
    records = get_store().list_all(statuses)
    return {"executions": records}


@app.get("/api/v1/executions/{execution_id}")
def get_execution(execution_id: str):
    rec = get_store().get(execution_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id!r} not found")
    return rec


# ── Parcels ───────────────────────────────────────────────────────────────────
@app.get("/api/parcels")
def list_parcels(
    crop: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
    limit: int = Query(120, le=500),
):
    _tools._load_parcels()
    results = list(_tools._PARCELS)
    if crop:
        results = [p for p in results if crop.lower() in (p.get("crop", {}) or {}).get("name", "").lower()]
    if zone:
        results = [p for p in results if zone.lower() == (p.get("zone") or "").lower()]
    return {"parcels": results[:limit], "total": len(results)}


@app.get("/api/parcels/{parcel_id}")
def get_parcel(parcel_id: str):
    _tools._load_parcels()
    p = _tools._PARCEL_BY_ID.get(parcel_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Parcel {parcel_id!r} not found")
    return p


@app.get("/api/history/{parcel_id}")
def get_history(parcel_id: str):
    """Five seasons of (dummy) yield / inputs / issues for one parcel, from data/history.csv."""
    import csv
    f = config.DATA_DIR / "history.csv"
    if not f.exists():
        raise HTTPException(status_code=404, detail="history.csv not found")
    with open(f, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("parcel_id") == parcel_id]
    if not rows:
        raise HTTPException(status_code=404, detail=f"No history for {parcel_id!r}")
    return {"parcel_id": parcel_id, "data_source": "dummy", "seasons": rows}


# ── Field report, alerts, satellite (deterministic, no LLM) ──────────────────
@app.get("/api/field-report/{parcel_id}")
def field_report(parcel_id: str, method: str = "sprinkler", pump_lps: float = Query(8.0, ge=0.5, le=200)):
    from app import field_report as fr
    rep = fr.build(parcel_id, method, pump_lps)
    if rep is None:
        raise HTTPException(status_code=404, detail=f"Parcel {parcel_id!r} not found")
    return rep


@app.post("/api/soil-test/{parcel_id}")
def soil_test(parcel_id: str, values: dict):
    """Rate a lab soil test (pH, EC, OC, N, P, K) and scale the TNAU fertiliser recommendations accordingly."""
    from app import advisory_extras as ex, field_report as fr
    _tools._load_parcels()
    p = _tools._PARCEL_BY_ID.get(parcel_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Parcel {parcel_id!r} not found")
    try:
        ev = ex.evaluate_soil_test(values)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Soil-test values must be numbers")
    ev["adjusted_fertilizer"] = fr.adjusted_fertilizer(p, ev["adjustment"])
    return ev


@app.get("/api/indices-export.csv")
def indices_export():
    """Bulk historical data: every parcel, every date, every index (Sentinel-2 and Sentinel-1)."""
    from fastapi.responses import Response
    from app import indices as ix
    d = ix._load()
    keys = list(ix.CATALOG)
    rows: dict[tuple[str, str], dict] = {}
    for k in keys:
        for pid, pts in d["series"].get(k, {}).items():
            for t, v in pts:
                rows.setdefault((pid, t), {})[k] = v
    out = ["parcel_id,date," + ",".join(keys)]
    for (pid, t) in sorted(rows):
        out.append(f"{pid},{t}," + ",".join("" if rows[(pid, t)].get(k) is None else str(rows[(pid, t)][k]) for k in keys))
    return Response("\n".join(out), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=then_malai_indices_all_parcels.csv"})


@app.get("/api/point")
def point_lookup(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    """Coordinate lookup: the value of every layer (latest month) at a lat/lon, and the parcel it falls in."""
    from app import layers_api
    return layers_api.lookup(lat, lon)


@app.get("/api/export/{name}.csv")
def export_csv(name: str):
    """Raw per-parcel observation files: ndvi_observations (6 Sentinel-2 indices + compass sectors) and radar_observations."""
    from fastapi.responses import FileResponse
    if name not in ("ndvi_observations", "radar_observations"):
        raise HTTPException(status_code=404, detail="Unknown export")
    f = config.DATA_DIR / "satellite" / f"{name}.csv"
    if not f.exists():
        raise HTTPException(status_code=404, detail="Not built yet")
    return FileResponse(f, media_type="text/csv", filename=f"then_malai_{name}.csv")


@app.get("/api/alerts")
def alerts(min_severity: str = Query("low", pattern="^(high|medium|low)$")):
    from app import field_report as fr
    return fr.all_alerts(min_severity)


@app.get("/api/village-brief")
def village_brief():
    from app import field_report as fr
    return fr.village_brief()


@app.get("/api/satellite")
def satellite_overview():
    from app import field_report as fr
    return fr.satellite_overview()


@app.get("/api/layers")
def layers_manifest():
    f = config.DATA_DIR / "layers" / "layers.json"
    if not f.exists():
        raise HTTPException(status_code=404, detail="layers.json not built yet (run scripts/build_layers.py)")
    return json.loads(f.read_text(encoding="utf-8"))


@app.get("/api/indices/{parcel_id}")
def index_results(parcel_id: str, start: Optional[str] = None, end: Optional[str] = None, indices: Optional[str] = None):
    """Per-parcel satellite index time series for a date window, with the previous window for comparison."""
    from app import indices as ix
    _tools._load_parcels()
    if parcel_id not in _tools._PARCEL_BY_ID:
        raise HTTPException(status_code=404, detail=f"Parcel {parcel_id!r} not found")
    try:
        sel = [i for i in (indices or "").split(",") if i in ix.CATALOG] or None
        out = ix.results(parcel_id, start, end, sel)
    except ValueError:
        raise HTTPException(status_code=400, detail="start/end must be YYYY-MM-DD")
    out["calendar"] = ix.calendar()
    out["field_directions"] = ix.field_directions(parcel_id)
    return out


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
