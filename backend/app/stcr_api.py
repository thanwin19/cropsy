"""stcr_api.py: POST /api/stcr (soil-test crop response calculator) and GET /api/stcr/example."""
from fastapi import APIRouter, HTTPException

from app import stcr

router = APIRouter()


@router.get("/api/stcr/example")
def example():
    return stcr.EXAMPLE


@router.get("/api/stcr/presets")
def presets():
    return {"items": stcr.PRESETS, "note": "Published TNAU equations. The soil series, not the district, decides which row applies: confirm it with your soil lab."}


@router.post("/api/stcr")
def run(payload: dict):
    try:
        coeffs = payload.get("coefficients") or (stcr.EXAMPLE["coefficients"] if payload.get("use_example") else None)
        if not coeffs:
            raise ValueError("send the equation coefficients from your soil lab or state STCR table (or use_example=true to see the arithmetic)")
        area = payload.get("area_ha")
        res = stcr.calculate(float(payload["target_q_ha"]), payload.get("soil") or {}, coeffs, float(area) if area else None, payload.get("organic_credit"))
        if not payload.get("coefficients"):
            res["example_warning"] = stcr.EXAMPLE["applies_to"]
        return res
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e))
