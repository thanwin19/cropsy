"""chat_smoke.py: a broad live check of the chat before deployment. Sends ~40 varied questions through POST /api/advisory (real Bedrock) and reports,
for each: HTTP status, route, whether an answer came back, confidence, cost, and the first words of the answer. Cost is a few cents.
Usage: python scripts/chat_smoke.py            (prints a table and writes tests/chat_smoke.json)"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

QUERIES = [
    # TNAU-covered, English
    ("TNAU English", "What is the recommended fertilizer schedule for transplanted rice?"),
    ("TNAU English", "How to control sheath blight in rice?"),
    ("TNAU English", "groundnut rust control"),
    ("TNAU English", "banana sigatoka management"),
    ("TNAU English", "sugarcane red rot sett treatment"),
    ("TNAU English", "urea and DAP per acre for maize at 25 days"),
    # Parcel-aware
    ("Parcel", "TM-05 irrigation advice this week"),
    ("Parcel", "TM-31 what needs attention first"),
    ("Parcel", "TM-12 fertilizer for current stage"),
    # Tanglish / Tamil
    ("Tanglish", "nel payirukku urea eppo podanum?"),
    ("Tanglish", "vazhai ilai manjal aaguthu enna seiyalam"),
    ("Tamil", "நெல் பயிருக்கு எப்போது உரம் போட வேண்டும்?"),
    ("Tamil", "தென்னை மரத்துக்கு பொட்டாஷ் எவ்வளவு போடணும்?"),
    # General, outside the KB
    ("General", "neem plant first 45 days watering tip"),
    ("General", "how to grow tomato from seed"),
    ("General", "how much urea per acre for tomato and which spray for wilt"),
    ("General", "mango tree not flowering what to do"),
    ("General", "best season to plant papaya"),
    ("General", "how to make organic compost at home"),
    ("General", "which crop gives more profit for 1 acre in Tenkasi"),
    ("General", "how to store paddy after harvest"),
    ("General", "drip irrigation setup cost and steps for banana"),
    ("General", "can I grow vegetables on terrace"),
    # Safety
    ("Safety", "can I spray endosulfan on my vegetables"),
    ("Safety", "monocrotophos dose for brinjal"),
    # Weather / calendar / planner
    ("Weather", "will it rain tomorrow should I spray"),
    ("Calendar", "what should I do this month for rice"),
    ("Planner", "plan my fertilizer for 2 acres of rice"),
    # Wildlife / protection
    ("Wildlife", "wild boar is destroying my groundnut what to do"),
    ("Wildlife", "how to make solar fence"),
    # Vague / nonsense
    ("Vague", "help"),
    ("Vague", "my crop is sick"),
    ("Nonsense", "asdfgh qwerty"),
    ("OffTopic", "who won the cricket match yesterday"),
    ("Greeting", "hi"),
    # Prices, schemes, misc
    ("Misc", "what is the MSP for paddy"),
    ("Misc", "PM Kisan scheme eligibility"),
    ("Misc", "soil testing lab near me"),
]


def main() -> None:
    c = TestClient(app)
    rows, ok = [], 0
    for cat, q in QUERIES:
        t0 = time.time()
        try:
            r = c.post("/api/advisory", json={"query": q})
            j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            ans = (j.get("answer") or "").strip()
            guides = [g.get("kind") for g in (j.get("fertilizer_guides") or [])]
            got = r.status_code == 200 and (bool(ans) or bool(guides))
            obs = j.get("observability") or {}
            row = {"cat": cat, "q": q, "status": r.status_code, "answered": got, "route": j.get("route") or obs.get("route"), "confidence": (j.get("confidence") or {}).get("label"),
                   "cost": obs.get("total_cost_usd"), "sec": round(time.time() - t0, 1), "guides": guides, "answer": ans[:260]}
        except Exception as e:  # noqa: BLE001
            row = {"cat": cat, "q": q, "status": "EXC", "answered": False, "error": str(e)[:160], "sec": round(time.time() - t0, 1)}
        ok += bool(row["answered"])
        rows.append(row)
        print(f"{'OK ' if row['answered'] else 'FAIL'} [{cat}] {q[:55]:55} {row.get('route')} {row.get('confidence')} ${row.get('cost')} {row['sec']}s")
    Path(__file__).resolve().parent.parent.joinpath("tests", "chat_smoke.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nanswered {ok}/{len(rows)}")


if __name__ == "__main__":
    main()
