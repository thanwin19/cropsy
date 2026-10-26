"""photo_findings.py: what a farmer's photo looked like, kept per parcel (the result only, never the photo) so recent photo evidence can feed the alerts."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app import aws_resources as aws
from app import config, events

_FILE = config.DATA_DIR / "photo_findings.jsonl"
_MAX = 300


def _read() -> list[dict]:
    if aws.enabled():
        return events.recent("photo_finding", _MAX)
    try:
        return [json.loads(x) for x in _FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
    except Exception:  # noqa: BLE001
        return []


def record_from_state(state) -> None:
    """Called after a photo question about a parcel: stores the nearest-reference-photo consensus."""
    try:
        ms = [m for m in (state.image_matches or []) if m.get("condition_code")]
        if not (state.parcel_id and ms):
            return
        votes: dict[str, list[float]] = {}
        for m in ms:
            votes.setdefault(m["condition_code"], []).append(float(m.get("similarity", 0.0)))
        code, sims = sorted(votes.items(), key=lambda kv: (-len(kv[1]), -sum(kv[1]) / len(kv[1])))[0]
        label = next(m.get("condition") for m in ms if m["condition_code"] == code)
        row = {"time": datetime.now(timezone.utc).isoformat(), "parcel_id": state.parcel_id, "condition_code": code, "label": label,
               "crop": next((m.get("crop") for m in ms if m["condition_code"] == code), ""), "votes": len(sims), "of": len(ms),
               "similarity": round(sum(sims) / len(sims), 3), "route": state.route}
        if aws.enabled():
            events.put("photo_finding", row)
            return
        rows = _read()[-(_MAX - 1):] + [row]
        _FILE.write_text(chr(10).join(json.dumps(r, ensure_ascii=False) for r in rows) + chr(10), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def recent_for(parcel_id: str, days: int = 21) -> list[dict]:
    cut = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for r in _read():
        try:
            if r["parcel_id"] == parcel_id and datetime.fromisoformat(r["time"]) >= cut:
                out.append(r)
        except Exception:  # noqa: BLE001
            continue
    return out


def clear() -> None:
    if aws.enabled():
        return                                     # misses.clear() empties every event kind in one go
    try:
        _FILE.unlink(missing_ok=True)
    except OSError:
        pass
