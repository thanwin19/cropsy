"""
model_bakeoff.py: which model should write the final answer on the cheap routes (ROUTINE / ADVISORY)?

It runs the same questions through the real pipeline once per candidate model (the writing step only; understanding, retrieval and the
verifier are identical) and compares quality, safety, speed and cost. Photo and complex questions are not included: they stay on Ministral 8B.
It also saves every answer so a person can read the Tamil and Tanglish ones side by side: automatic checks cannot judge Tamil quality.

Needs AWS (about 70 short calls, roughly 1 US cent in all):   aws sso login --profile FAI-TCE-Builder-AI-402365884845
Usage: python tests/model_bakeoff.py [--models nova-micro,ministral-3b,ministral-8b] [--limit 25]
Result: tests/bakeoff_report.json and a table on screen. Adopt a model only if it matches Nova Micro on safety and verifier passes at equal or lower cost.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, pipeline  # noqa: E402
from app.schemas import AdvisoryRequest  # noqa: E402

HERE = Path(__file__).resolve().parent
CANDIDATES = {"nova-micro": config.MODEL_NOVA_MICRO, "ministral-3b": config.MODEL_MINISTRAL_3B, "ministral-8b": config.MODEL_MINISTRAL_8B, "nova-lite": config.MODEL_NOVA_LITE}
REFUSAL = re.compile(r"(not (specified|mentioned|available|provided|found)|evidence not available|cannot give|no verified)", re.IGNORECASE)
TAMILISH = re.compile(r"[஀-௿]|\b(evlo|podanum|eppo|eppadi|payir|nel|vayal|thanni|uram|maruthu)\b", re.IGNORECASE)


def questions(limit: int) -> list[dict]:
    qs = []
    for x in json.loads((config.DATA_DIR / "queries.json").read_text(encoding="utf-8")):
        if x.get("expected_route") == "ADVISORY" and not x.get("image"):
            qs.append({"id": x["id"], "query": x["query"], "parcel_id": x.get("parcel_id"), "must_not": []})
    for c in json.loads((HERE / "eval_set.json").read_text(encoding="utf-8")):
        if c["group"] in ("not_blocked", "quality", "safety") and c["expect"] == "advisory":
            qs.append({"id": c["id"], "query": c["query"], "parcel_id": c.get("parcel_id"), "must_not": c.get("must_not", [])})
    seen, out = set(), []
    for q in qs:
        if q["query"] not in seen:
            seen.add(q["query"])
            out.append(q)
    return out[:limit]


def run(model_key: str, qs: list[dict]) -> list[dict]:
    os.environ["CROPSY_SYNTH_MODEL"] = CANDIDATES[model_key]
    rows = []
    for q in qs:
        t0 = time.time()
        try:
            r = pipeline.run(AdvisoryRequest(query=q["query"], parcel_id=q["parcel_id"]))
            text = " ".join([r.answer or ""] + (r.recommendations or []) + (r.risks or []))
            rows.append({"id": q["id"], "query": q["query"], "route": r.route, "answer": (r.answer or "")[:500], "sources": len(r.sources or []),
                         "verified": r.verified, "refusal": bool(REFUSAL.search(r.answer or "")), "unsafe": [x for x in q["must_not"] if re.search(x, text, re.I)],
                         "cost": r.estimated_cost_usd or 0.0, "secs": round(time.time() - t0, 1), "confidence": (r.confidence or {}).get("level"),
                         "tamilish": bool(TAMILISH.search(q["query"]))})
        except Exception as e:  # noqa: BLE001
            rows.append({"id": q["id"], "query": q["query"], "error": repr(e)[:120], "cost": 0.0, "secs": round(time.time() - t0, 1)})
    return rows


def summary(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    n = max(1, len(ok))
    tam = [r for r in ok if r["tamilish"]]
    return {"n": len(rows), "errors": len(rows) - len(ok), "verifier_pass": sum(1 for r in ok if r["verified"]), "with_sources": sum(1 for r in ok if r["sources"]),
            "refusals": sum(1 for r in ok if r["refusal"]), "unsafe": sum(1 for r in ok if r["unsafe"]), "tamil_or_tanglish": len(tam),
            "tamil_refusals": sum(1 for r in tam if r["refusal"]), "avg_secs": round(sum(r["secs"] for r in ok) / n, 1), "total_cost_usd": round(sum(r["cost"] for r in rows), 5)}


def main() -> None:
    args = sys.argv[1:]
    models = (args[args.index("--models") + 1] if "--models" in args else "nova-micro,ministral-3b,ministral-8b").split(",")
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 30
    qs = questions(80)
    if "--tamil" in args:                                   # only Tamil / Tanglish questions
        qs = [q for q in qs if TAMILISH.search(q["query"])]
    qs = qs[:limit]
    print(f"{len(qs)} questions x {len(models)} models")
    report = {}
    for m in models:
        rows = run(m, qs)
        report[m] = {"summary": summary(rows), "rows": rows}
        print(f"{m:13s}", report[m]["summary"])
    (HERE / "bakeoff_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("answers saved to tests/bakeoff_report.json: read the Tamil/Tanglish ones side by side before choosing")


if __name__ == "__main__":
    main()
