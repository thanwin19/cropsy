"""misses.py: a small log of questions Cropsy did not understand, so the team can see what farmers ask and add guidance for it."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app import aws_resources as aws
from app import config, events

_FILE = config.DATA_DIR / "misses.jsonl"
_MAX = 500


def record(query: str, parcel_id: str | None, kind: str) -> None:
    try:
        if aws.enabled():
            events.put("miss", {"time": datetime.now(timezone.utc).isoformat(), "query": (query or "")[:300], "parcel_id": parcel_id, "kind": kind})
            return
        rows = recent(_MAX - 1)
        rows.append({"time": datetime.now(timezone.utc).isoformat(), "query": (query or "")[:300], "parcel_id": parcel_id, "kind": kind})
        _FILE.write_text(chr(10).join(json.dumps(r, ensure_ascii=False) for r in rows) + chr(10), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def clear() -> None:
    if aws.enabled():
        try:
            events.clear()
        except Exception:  # noqa: BLE001
            pass
        return
    try:
        _FILE.unlink(missing_ok=True)
        (config.DATA_DIR / "feedback.jsonl").unlink(missing_ok=True)
        (config.DATA_DIR / "photo_findings.jsonl").unlink(missing_ok=True)
    except OSError:
        pass


def recent(n: int = 100) -> list[dict]:
    if aws.enabled():
        return events.recent("miss", n)
    try:
        rows = [json.loads(x) for x in _FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
    except Exception:  # noqa: BLE001
        return []
    return rows[-n:]


# ── farmer feedback (thumbs) for the officer review list ─────────────────────────────────────────────────────────
_FB = config.DATA_DIR / "feedback.jsonl"


def record_feedback(row: dict) -> None:
    try:
        if aws.enabled():
            events.put("feedback", {**row, "time": datetime.now(timezone.utc).isoformat()})
            return
        rows = feedback_recent(_MAX - 1)
        rows.append({**row, "time": datetime.now(timezone.utc).isoformat()})
        _FB.write_text(chr(10).join(json.dumps(r, ensure_ascii=False) for r in rows) + chr(10), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def feedback_recent(n: int = 100) -> list[dict]:
    if aws.enabled():
        return events.recent("feedback", n)
    try:
        rows = [json.loads(x) for x in _FB.read_text(encoding="utf-8").splitlines() if x.strip()]
    except Exception:  # noqa: BLE001
        return []
    return rows[-n:]
