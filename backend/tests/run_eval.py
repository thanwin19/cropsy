"""
run_eval.py: evaluation of Cropsy against tests/eval_set.json (farmer-style questions in English, Tamil, Tanglish, with typos and nonsense).

Measures
  route accuracy      did the question go where it should (clarify card, emergency card, guide card, facts, or normal advisory)?
  not-blocked rate    clear questions with typos or Tanglish must NOT be stopped by the not-understood check
  citation rate       live advisory answers must carry at least one source
  unsafe-answer rate  answers that break a "must_not" rule (for example an invented chemical dose) / all answers checked
  confidence shown    live answers must carry a confidence label

Offline (default): costs nothing and uses no AWS; it checks everything decided before the model is called.
--live            also sends the cases marked "live" through the real pipeline (a few Bedrock calls, about 1 cent in all).

Usage: python tests/run_eval.py [--live] [--group not_understood]
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import pipeline  # noqa: E402
from app.schemas import AdvisoryRequest, PipelineState  # noqa: E402
from app.steps import facts, guides, tools  # noqa: E402

HERE = Path(__file__).resolve().parent


def _state(c: dict) -> PipelineState:
    tools._load_parcels()
    p = tools._PARCEL_BY_ID.get(c["parcel_id"]) if c.get("parcel_id") else None
    return PipelineState(query=c["query"], parcel_id=c.get("parcel_id"), parcel_context=p)


def offline(c: dict) -> tuple[bool, str]:
    st = _state(c)
    cards = guides.guide_only(st)
    got = cards[0]["id"] if cards else None
    exp = c["expect"]
    if exp.startswith("card:"):
        want = exp[5:]
        # fence questions may legitimately open either fence card first
        ok = got == want or (want.startswith("fence") and bool(got) and got.startswith("fence"))
        return ok, f"card={got}"
    if exp == "facts":
        topics = facts.topics_asked(c["query"].lower())
        return bool(topics) and not cards, f"topics={topics} card={got}"
    if exp == "advisory":
        return not cards and not guides.is_emergency(st), f"card={got}"
    return False, "unknown expectation"


def live(c: dict) -> dict:
    t0 = time.time()
    r = pipeline.run(AdvisoryRequest(query=c["query"], parcel_id=c.get("parcel_id")))
    text = " ".join([r.answer or ""] + (r.recommendations or []) + (r.risks or []))
    bad = [rx for rx in c["must_not"] if re.search(rx, text, re.IGNORECASE)]
    return {"route": r.route, "sources": len(r.sources or []), "confidence": (r.confidence or {}).get("label"), "unsafe": bad, "secs": round(time.time() - t0, 1),
            "cost": r.estimated_cost_usd, "text": (r.answer or "")[:140]}


def main() -> None:
    args = sys.argv[1:]
    do_live = "--live" in args
    group = args[args.index("--group") + 1] if "--group" in args else None
    cases = [c for c in json.loads((HERE / "eval_set.json").read_text(encoding="utf-8")) if not group or c["group"] == group]
    rows, by_group = [], {}
    for c in cases:
        ok, info = offline(c)
        row = {"id": c["id"], "group": c["group"], "query": c["query"], "expect": c["expect"], "route_ok": ok, "info": info}
        by_group.setdefault(c["group"], []).append(ok)
        if do_live and c["live"]:
            row["live"] = live(c)
        rows.append(row)

    def rate(g: str) -> str:
        v = by_group.get(g, [])
        return f"{sum(v)}/{len(v)}" if v else "n/a"

    print("ROUTE ACCURACY (offline, no AWS)")
    for g in by_group:
        print(f"  {g:15s} {rate(g)}")
    tot = [r["route_ok"] for r in rows]
    print(f"  {'ALL':15s} {sum(tot)}/{len(tot)}  = {100 * sum(tot) / max(1, len(tot)):.0f}%")
    nb = by_group.get("not_blocked", [])
    if nb:
        print(f"NOT-BLOCKED RATE (typo / Tanglish / Tamil clear questions reach the normal answer): {sum(nb)}/{len(nb)}")
    lv = [r["live"] for r in rows if "live" in r]
    if lv:
        cited = sum(1 for x in lv if x["sources"] > 0)
        conf = sum(1 for x in lv if x["confidence"])
        unsafe = sum(1 for x in lv if x["unsafe"])
        print(f"LIVE ({len(lv)} answers, cost ${sum(x['cost'] or 0 for x in lv):.5f})")
        print(f"  citation rate         {cited}/{len(lv)}")
        print(f"  confidence label      {conf}/{len(lv)}")
        print(f"  unsafe-answer rate    {unsafe}/{len(lv)}")
        for r in rows:
            if "live" in r:
                x = r["live"]
                print(f"    {r['id']} {r['query'][:44]:44s} route={x['route']} sources={x['sources']} conf={x['confidence']} unsafe={x['unsafe']}")
    failed = [r for r in rows if not r["route_ok"]]
    if failed:
        print("FAILED ROUTES")
        for r in failed:
            print(f"  {r['id']} [{r['group']}] {r['query']!r}: expected {r['expect']}, {r['info']}")
    (HERE / "eval_report.json").write_text(json.dumps({"rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
