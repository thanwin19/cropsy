"""field_api.py: GET /api/field-health/{parcel}: satellite evidence with provenance, and pixel-level zones inside the parcel (for the map overlay)."""
from fastapi import APIRouter, HTTPException

from app import field_analysis

router = APIRouter()


@router.get("/api/field-health/{parcel_id}")
def field_health(parcel_id: str, layer: str = "ndvi", month: str | None = None):
    pid = parcel_id.strip().upper()
    if pid not in field_analysis._rings():
        raise HTTPException(status_code=404, detail=f"unknown parcel {pid}")
    try:
        return {"parcel_id": pid, "evidence": field_analysis.canonical(pid), "zones": field_analysis.zones(pid, layer, month)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"field analysis failed: {str(e)[:120]}")
