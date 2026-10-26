"""
eval_ecr.py: Expert Compliance Rate. Not "is the answer correct?" but "does the answer give the reason an agronomist would give?".

An agriculture expert fills one sentence of key reasoning per question in tests/expert_rationales.json (blank ones are skipped; nothing is invented here).
For each filled one this runs the real pipeline once and asks Nova Micro whether the answer contains that reasoning.
AWS use is small: 1 answer + 1 short judge call per filled question (about 0.03 US cent each). Use --ids Q02,Q05 to run only some.
Usage: python tests/eval_ecr.py [--ids Q02,Q05]        Result: tests/ecr_report.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, pipeline  # noqa: E402
from app.models import bedrock  # noqa: E402
from app.schemas import AdvisoryRequest  # noqa: E402

HERE = Path(__file__).resolve().parent
JUDGE = ("You check whether an answer gives the key reasoning an expert would give. Return JSON only: "
         '{"ecr_pass": true|false, "missing": "what key element is missing, or empty"}. Be strict: the idea must be present, not just related words.')


def main() -> None:
    items = json.loads((HERE / "expert_rationales.json").read_text(encoding="utf-8"))["items"]
    only = set(sys.argv[sys.argv.index("--ids") + 1].split(",")) if "--ids" in sys.argv else None
    rows = []
    for qid, it in items.items():
        if not it.get("expert_rationale", "").strip() or (only and qid not in only):
            continue
        r = pipeline.run(AdvisoryRequest(query=it["query"], parcel_id=it.get("parcel_id")))
        answer = " ".join([r.answer or ""] + (r.recommendations or []))
        text, _tok, _ = bedrock.invoke_text(config.MODEL_NOVA_MICRO, f"EXPERT KEY REASONING: {it['expert_rationale']}\n\nANSWER: {answer[:1800]}", system=JUDGE, max_tokens=120)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        v = json.loads(m.group()) if m else {"ecr_pass": False, "missing": "judge returned no JSON"}
        rows.append({"id": qid, "query": it["query"], "pass": bool(v.get("ecr_pass")), "missing": v.get("missing", ""), "answer": (r.answer or "")[:300], "verifier": r.verified})
        print(qid, "PASS" if rows[-1]["pass"] else f"FAIL: {rows[-1]['missing']}")
    n = len(rows)
    print(f"Expert Compliance Rate: {sum(r['pass'] for r in rows)}/{n}" if n else "No rationales filled in yet: ask an agronomist to complete tests/expert_rationales.json")
    (HERE / "ecr_report.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
