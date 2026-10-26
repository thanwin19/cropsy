"""corrections_api.py: officer corrections endpoints. Writing needs the officer key (env CROPSY_OFFICER_KEY); with no key set, only this computer (localhost) may write."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from app import corrections

router = APIRouter()


def _allowed(request: Request, key: Optional[str]) -> bool:
    want = os.getenv("CROPSY_OFFICER_KEY", "")
    if want:
        return key == want
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost")


@router.get("/api/corrections")
def list_corrections(limit: int = 100):
    return {"items": list(reversed(corrections.all_rows(min(max(limit, 1), 500))))}


@router.post("/api/corrections")
def add_correction(payload: dict, request: Request, x_officer_key: Optional[str] = Header(None)):
    if not _allowed(request, x_officer_key):
        raise HTTPException(status_code=403, detail="Officer key required")
    q, a, who = str(payload.get("query", "")).strip(), str(payload.get("corrected_answer", "")).strip(), str(payload.get("officer", "")).strip()
    if len(q) < 3 or len(a) < 10 or not who:
        raise HTTPException(status_code=422, detail="query, corrected_answer (10+ characters) and officer name are required")
    return corrections.add(q, a, who, payload.get("parcel_id"), payload.get("note"))


@router.delete("/api/corrections/{cid}")
def delete_correction(cid: str, request: Request, x_officer_key: Optional[str] = Header(None)):
    if not _allowed(request, x_officer_key):
        raise HTTPException(status_code=403, detail="Officer key required")
    return {"removed": corrections.remove(cid)}
