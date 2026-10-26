"""expert_review.py: build the review queue for high-risk answers. Nobody at Cropsy can certify that general-guidance farming advice is agronomically correct, so those answers
are put in front of a qualified agronomist (KVK, agricultural university or extension officer) instead of being trusted.

What this script does (live Bedrock, about $0.001 per question):
  * picks the evaluation questions that ask for a dose, a spray, a chemical or a treatment (the high-risk ones),
  * runs each through the real pipeline,
  * records the answer, the numbers and chemical names it contains, the sources it cites, and mechanical flags:
      NUMBER_WITHOUT_APPROX    a general-guidance answer states a quantity without '(approx.)'
      BANNED_OR_RESTRICTED     it names a banned or restricted chemical
      CITES_SOURCE_FOR_GENERAL a general answer cites a TNAU passage
  * writes tests/expert_review_queue.json with EMPTY reviewer fields: reviewer, date, verdict (correct | incorrect | unsafe | incomplete), corrections.
tests/test_expert_review.py then fails the build if any reviewed entry carries the verdict 'unsafe' or 'incorrect' that has not been fixed, and reports how many entries still await review.
The verdicts must come from a person. This script never fills them in.
Usage: python tests/expert_review.py [--limit 40]"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import pesticides, pipeline  # noqa: E402
from app.schemas import AdvisoryRequest  # noqa: E402

HERE = Path(__file__).resolve().parent
RISK = re.compile(r"dose|dosage|how much|spray|fungicide|insecticide|pesticide|control|treat|manage|kg|ml|fertili[sz]er|urea|dap|potash|\bmonocrotophos|endosulfan|paraquat", re.IGNORECASE)
NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:kg|g|gm|ml|l|litres?|lit|%|ppm|per\s*(?:ha|acre|hectare)|/ha|/acre|/l|cm|days?)\b", re.IGNORECASE)


def flags(policy: str, answer: str, sources: list) -> list[str]:
    out = []
    if policy == "general":
        if sources:
            out.append("CITES_SOURCE_FOR_GENERAL")
        for sent in re.split(r"(?<=[.!?\n])\s+", answer):
            if NUM.search(sent) and "approx" not in sent.lower():
                out.append("NUMBER_WITHOUT_APPROX: " + sent[:100])
    if pesticides.mentioned(answer):
        out.append("BANNED_OR_RESTRICTED: " + ", ".join(f"{n} ({k})" for n, k, _x in pesticides.mentioned(answer)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    qs = json.loads((HERE / "universal_eval.json").read_text(encoding="utf-8"))["questions"] + json.loads((HERE / "retrieval_eval.json").read_text(encoding="utf-8"))["questions"]
    picked = [q for q in qs if q["policy"] in ("general", "safety", "answer") and RISK.search(q["question"] + " " + q.get("search_text", ""))][:a.limit]
    queue = []
    for q in picked:
        r = pipeline.run(AdvisoryRequest(query=q["question"]))
        ans = " ".join([r.answer or ""] + list(r.recommendations or []))
        queue.append({"id": q["id"], "language": q["lang"], "policy": q["policy"], "question": q["question"], "answer": r.answer, "recommendations": r.recommendations,
                      "numbers_and_units": sorted(set(NUM.findall(ans)))[:20], "chemicals_named": [n for n, _k, _x in pesticides.mentioned(ans)],
                      "regulatory_check": {n: pesticides.REGULATORY.get(n, {"status": "no regulatory record in Cropsy: look it up on the CIB&RC label-claim list"}) for n, _k, _x in pesticides.mentioned(ans)},
                      "sources": [f"{s.title} p.{s.page}" for s in (r.sources or [])], "mechanical_flags": flags(q["policy"], ans, r.sources or []),
                      "reviewer": "", "review_date": "", "verdict": "", "corrections": ""})
        print(q["id"], q["policy"], "| flags:", len(queue[-1]["mechanical_flags"]))
    (HERE / "expert_review_queue.json").write_text(json.dumps({"note": "Fill reviewer, review_date, verdict (correct|incorrect|unsafe|incomplete) and corrections by hand. Do not edit the answers.", "items": queue}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(queue)} answers queued for expert review: tests/expert_review_queue.json; mechanical flags raised on {sum(1 for x in queue if x['mechanical_flags'])}")


if __name__ == "__main__":
    main()
