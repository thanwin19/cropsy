"""
corrections.py: answers an agriculture officer has reviewed and corrected.

When a farmer asks (nearly) the same question again, the officer's text is shown instead of a model answer, marked as officer-reviewed.
Stored like the other small logs: a local file, or the DynamoDB events table when CROPSY_STORE=aws. Officer corrections are guidance, not
personal data, so "delete my data" leaves them in place.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from app import aws_resources as aws
from app import config, events

_FILE = config.DATA_DIR / "corrections.jsonl"
_MAX = 500
MIN_SIMILARITY = 0.8


def _tokens(q: str) -> set[str]:
    return set(re.findall(r"\w+", (q or "").lower()))


def all_rows(n: int = _MAX) -> list[dict]:
    try:
        if aws.enabled():
            return events.recent("correction", n)
        return [json.loads(x) for x in _FILE.read_text(encoding="utf-8").splitlines() if x.strip()][-n:]
    except Exception:  # noqa: BLE001
        return []


def add(query: str, corrected_answer: str, officer: str, parcel_id: str | None = None, note: str | None = None) -> dict:
    row = {"id": uuid.uuid4().hex[:8], "time": datetime.now(timezone.utc).isoformat(), "query": (query or "").strip()[:300],
           "corrected_answer": (corrected_answer or "").strip()[:2000], "officer": (officer or "").strip()[:80], "parcel_id": parcel_id or None, "note": (note or "")[:300]}
    if aws.enabled():
        events.put("correction", row)
    else:
        rows = all_rows(_MAX - 1) + [row]
        _FILE.write_text(chr(10).join(json.dumps(r, ensure_ascii=False) for r in rows) + chr(10), encoding="utf-8")
    return row


def remove(cid: str) -> bool:
    if aws.enabled():
        return False                      # the events table is append-only; add a newer correction instead
    rows = all_rows()
    keep = [r for r in rows if r.get("id") != cid]
    if len(keep) == len(rows):
        return False
    _FILE.write_text(chr(10).join(json.dumps(r, ensure_ascii=False) for r in keep) + (chr(10) if keep else ""), encoding="utf-8")
    return True


def find(query: str, parcel_id: str | None = None) -> dict | None:
    """The best officer correction for this question (word overlap of at least 0.8), or None."""
    q = _tokens(query)
    if len(q) < 2:
        return None
    best, best_s = None, 0.0
    for r in reversed(all_rows()):        # newest first, so a later correction wins a tie
        if r.get("parcel_id") and r["parcel_id"] != parcel_id:
            continue
        t = _tokens(r.get("query", ""))
        if len(t) < 2:
            continue
        s = len(q & t) / len(q | t)
        if s >= MIN_SIMILARITY and s > best_s:
            best, best_s = r, s
    return best
