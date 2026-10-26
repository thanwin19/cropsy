"""
priority.py: one ranked "what needs attention first" list per parcel and for the village, with the reasons shown.

It joins four sources by fixed rules (no language model, no AWS):
  weather    the 7-day forecast (rain, heat) from the village forecast
  crop stage how sensitive the crop is right now (flowering, silking, grain filling... matter more than early growth)
  satellite  the Sentinel-2 greenness trend (stress or watch)
  record     the parcel's recorded issue and how often the parcel had the same trouble in past seasons (history file)

The score (0 to 100) only orders the list. Every point is traced to a reason with its source, and the dummy parts of the data are labelled.
"""
from __future__ import annotations

import csv
import re
from collections import Counter

from datetime import datetime, timezone

from app import config, photo_findings
from app import field_report as fr
from app.steps import tools

CRITICAL = re.compile(r"flower|panicle|silking|tasseling|grain filling|milk|dough|boll|peg|pod|rhizome|bunch|shooting|fruit|grand growth", re.IGNORECASE)
SEV_POINTS = {"severe": 40, "moderate": 24, "mild": 10}
LEVELS = [(70, "urgent"), (45, "high"), (25, "watch"), (0, "routine")]


def _history() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    try:
        with open(config.DATA_DIR / "history.csv", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                out.setdefault(r["parcel_id"], []).append(r)
    except Exception:  # noqa: BLE001
        pass
    return out


def _level(score: float) -> str:
    return next(name for cut, name in LEVELS if score >= cut)


def score_parcel(p: dict, fc: list[dict], fc_src: str, sat: dict | None, hist: list[dict], expo: dict | None = None) -> dict:
    pid, crop = p["parcel_id"], p["crop"]["name"]
    stage = str(p["crop"].get("stage", "")).split(" - ")[0]
    critical = bool(CRITICAL.search(stage))
    weight = 1.0 if critical else 0.6
    pts = 0.0
    why: list[dict] = []
    actions: list[str] = []

    def add(points: float, text: str, source: str, action: str | None = None):
        nonlocal pts
        pts += points
        why.append({"points": round(points), "text": text, "source": source})
        if action and action not in actions:
            actions.append(action)

    rain3 = sum(d["rain_mm"] for d in fc[:3])
    low_lying = p.get("zone") == "valley" or (p.get("terrain") or {}).get("waterlogging_susceptibility") == "high"
    past = Counter(r["major_issue"] for r in hist)
    wet_hist = past.get("heavy rain lodging", 0)
    dry_hist = past.get("dry spell stress", 0)
    live = "live forecast" if fc_src == "live" else "sample forecast"

    if rain3 >= fr.HEAVY_RAIN_3D_MM:
        base = 22 * weight + (10 if low_lying and crop != "Rice" else 0)
        add(base, f"{rain3:.0f} mm of rain expected in 3 days{' on a low-lying parcel' if low_lying else ''}; the crop is at {stage or 'an unknown stage'}"
                  f"{' (a sensitive stage)' if critical else ''}", f"weather ({live}) + crop stage",
            "Clear drains; hold sprays and fertilizer until the rain passes.")
        if wet_hist >= 2:
            add(12, f"this parcel lost yield to heavy-rain lodging in {wet_hist} of its last {len(hist)} seasons", "history (sample data)")
    elif sum(d["rain_mm"] for d in fc[:5]) < 3 and crop != "Rice":
        defi = fr._irrigation_deficit(p)
        if defi is not None and defi >= fr.IRRIGATION_DEFICIT_MM:
            add(18 * weight + (6 if dry_hist >= 2 else 0), f"about {defi} mm of water used since the last irrigation and almost no rain coming; stage {stage}", "weather + water balance (sample history)",
                "Irrigate early morning or evening.")
            if dry_hist >= 2:
                add(8, f"dry-spell stress hit this parcel in {dry_hist} past seasons", "history (sample data)")
    hot = max((d.get("tmax_c") or d.get("tmax") or 0) for d in fc[:5]) if fc else 0
    if hot >= 38 and critical:
        add(12, f"very hot days ({hot:.0f} C) while the crop is at a sensitive stage", f"weather ({live}) + crop stage", "Irrigate in the cool hours and mulch.")

    if sat and sat.get("status") in ("stress", "watch"):
        pts_s = 30 if sat["status"] == "stress" else 15
        add(pts_s * (1.15 if critical else 1.0), f"satellite greenness is {'falling' if sat['status'] == 'stress' else 'dipping'}: NDVI {sat.get('latest_ndvi')} versus recent baseline {sat.get('baseline_ndvi')}",
            "Sentinel-2 (real)", "Inspect the field this week and photograph affected plants.")

    for f in photo_findings.recent_for(pid):
        if f["condition_code"] in ("healthy", "field_scene") or f["votes"] < 3 or f["similarity"] < 0.55:
            continue
        age = max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(f["time"])).total_seconds() / 86400)
        add(26 * (f["votes"] / max(1, f["of"])) * max(0.35, 1 - age / 21), f"a photo sent {age:.0f} day(s) ago looked like {f['label']} ({f['votes']} of {f['of']} nearest reference photos, similarity {f['similarity']})",
            "your photo (live analysis)", "Check the plants shown in the photo and ask Cropsy for the TNAU advice for " + str(f["label"]) + ".")

    ex = (expo or {}).get(pid)
    if ex and ex["risk"] >= 10:                                    # downwind of an infected parcel (village spread scenario model)
        add(min(22.0, 0.35 * ex["risk"]) * (1.0 if critical else 0.8), f"downwind of {ex['source']} ({ex['disease']}): spread risk {ex['risk']:.0f}/100 within 72 h, {ex['distance_m']} m away" + (f", about {ex['hours']} h to threshold" if ex.get("hours") else ""),
            "village spread model (scenario, assumptions)", "Inspect leaves today and ask your agriculture officer or KVK about preventive action.")

    issue = p.get("observed_issue") or {}
    if issue.get("code") not in (None, "healthy") and issue.get("severity") in SEV_POINTS:
        label = issue.get("label")
        again = past.get(label, 0)
        # dummy records must not outrank real signals: cap the record's own share
        add(min(SEV_POINTS[issue["severity"]], 28) * (1.0 if critical else 0.8), f"recorded issue: {label} ({issue['severity']}, {issue.get('since_days')} days ago)", "parcel record (dummy)",
            "Ask Cropsy for the TNAU advice or upload a photo.")
        if again >= 1:
            add(8, f"{label} also appeared in {again} earlier season(s) on this parcel", "history (sample data)")

    score = min(100.0, round(pts))
    if not why:
        why.append({"points": 0, "text": "no weather, satellite or record signal needs action now", "source": "all four sources checked"})
    return {"parcel_id": pid, "crop": crop, "stage": stage, "score": score, "level": _level(score), "reasons": why,
            "action": actions[0] if actions else "Routine care.", "actions": actions}


def ranked(parcel_id: str | None = None, limit: int = 10) -> dict:
    tools._load_parcels()
    fc, src = fr.village_forecast()
    sat_all = (tools._load_satellite().get("parcels") or {})
    hist = _history()
    try:
        from app import spread
        expo = spread.village_exposure()
    except Exception:  # noqa: BLE001
        expo = {}
    rows = [score_parcel(p, fc, src, sat_all.get(p["parcel_id"]), hist.get(p["parcel_id"], []), expo) for p in tools._PARCELS
            if parcel_id is None or p["parcel_id"] == parcel_id]
    rows.sort(key=lambda r: (-r["score"], r["parcel_id"]))
    return {"forecast_source": src, "count": len(rows), "items": rows[:limit],
            "how": "Score 0 to 100 from weather, crop stage, satellite trend and the parcel's record and history. It only orders the list; each reason shows its source. "
                   "Record and history are dummy data; satellite and forecast are real."}
