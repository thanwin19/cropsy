"""run_gold_live.py: run the manually written gold set (tests/gold_set.json) through the live pipeline (needs AWS login) and score separately:
  relevance/numbers  every 'all' pattern is in the answer + recommendations and no 'forbid' pattern is
  citation           the cited pages are among the gold pages (and nothing is cited for no_info / general / clarify / card answers)
  behaviour          the answer type is the expected one (answer, no_info, clarify, general, card)
Usage: python tests/run_gold_live.py [--ids Q01,Q02] [--json out.json]
These are automatic pattern checks on values the author read from the source passages; they are not an expert review."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

NO_INFO = re.compile(r"not (specified|provided|mentioned|found|available)|do not have|don't have|cannot|no verified|could not find", re.I)


def behaviour(r: dict) -> str:
    ans = r.get("answer") or ""
    rt = r.get("route")
    if r.get("parcel_context"):
        return "answer"
    if r.get("confidence", {}).get("label") == "I need more detail" or "Which crop" in ans or "could not find that parcel" in ans:
        return "clarify"
    if "does not hold" in ans or "market (mandi) prices" in ans:
        return "card"
    if (r.get("confidence") or {}).get("why", [""])[0].startswith("General guidance"):
        return "general"
    if not r.get("sources") and NO_INFO.search(ans):
        return "no_info"
    return "answer"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids")
    ap.add_argument("--json")
    a = ap.parse_args()
    qs = json.load(open(Path(__file__).parent / "gold_set.json", encoding="utf-8"))["questions"]
    if a.ids:
        qs = [q for q in qs if q["id"] in a.ids.split(",")]
    c = TestClient(app)
    rows, tot = [], {"numbers": [], "citation": [], "behaviour": []}
    for q in qs:
        ctx = None
        if q.get("follow"):
            r0 = c.post("/api/advisory", json={"query": q["q"], "region": q.get("region")}).json()
            ctx = r0.get("crop")
        body = {"query": q.get("follow") or q["q"], "region": q.get("region"), "context_crop": ctx}
        r = c.post("/api/advisory", json=body).json()
        text = " ".join([r.get("answer") or ""] + (r.get("recommendations") or []))
        pages = [s.get("page") for s in (r.get("sources") or []) if str(s.get("page") or "").isdigit()]       # web portal sources carry a section label, not a page
        why = []
        num_ok = all(re.search(p, text, re.I) for p in q.get("all", [])) and not any(re.search(p, text, re.I) for p in q.get("forbid", []))
        if not num_ok:
            why.append("values: missing " + str([p for p in q.get("all", []) if not re.search(p, text, re.I)]) + " forbidden-hit " + str([p for p in q.get("forbid", []) if re.search(p, text, re.I)]))
        if q["behavior"] == "answer" and q.get("pages"):
            cit_ok = (bool(pages) or q.get("pages_optional", False)) and all(p in q["pages"] for p in pages)
        else:
            cit_ok = not (r.get("sources") or []) if q["behavior"] in ("no_info", "general", "clarify", "card") else True
        if not cit_ok:
            why.append(f"citation: cited pages {pages}, expected {q.get('pages') or 'none'}")
        got = behaviour(r)
        beh_ok = got == q["behavior"]
        if not beh_ok:
            why.append(f"behaviour: got {got}, expected {q['behavior']}")
        for k, v in (("numbers", num_ok), ("citation", cit_ok), ("behaviour", beh_ok)):
            tot[k].append(v)
        rows.append({"id": q["id"], "q": q["q"], "ok": not why, "why": why, "answer": text[:400], "pages": pages})
        print(("OK  " if not why else "FAIL"), q["id"], "|", q["q"][:46].encode("ascii", "replace").decode(), "|", "; ".join(why)[:200])
    print()
    for k, v in tot.items():
        print(f"  {k:10s} {sum(v)}/{len(v)}")
    if a.json:
        json.dump(rows, open(a.json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
