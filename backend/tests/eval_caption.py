"""
eval_caption.py: does Caption -> Judge -> Check help on held-out field photos?

For each held-out photo (never used as a reference): write the caption, judge it, find the nearest reference photos, and let the caption choose a
condition from the crop's catalogue. It then reports
  * how often the caption passed the judge, was rewritten by the judge, or needed a second caption
  * how often a crop or disease name leaked into the caption (should be 0 after the judge)
  * accuracy of the reference-photo match, of the caption's own choice, and of the cases where the two AGREE or DISAGREE
    (if "agree" is much more accurate than "disagree", then flagging disagreement as uncertain protects the farmer)
  * average cost and time per photo

Needs AWS (about 3 small model calls and 1 image embedding per photo; 40 photos cost roughly 1 US cent):
    aws sso login --profile FAI-TCE-Builder-AI-402365884845
Usage: python tests/eval_caption.py [--n 40]      Result: tests/caption_eval.json
"""
from __future__ import annotations

import base64
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.schemas import PipelineState  # noqa: E402
from app.steps import caption, retrieve  # noqa: E402

HERE = Path(__file__).resolve().parent
IMG = config.DATA_DIR / "images"


def pick(n: int) -> list[dict]:
    items = [i for i in json.loads((IMG / "manifest.json").read_text(encoding="utf-8"))["items"]
             if i.get("split") == "holdout" and i.get("condition_code") not in ("field_scene",)]
    by = defaultdict(list)
    for i in items:
        by[i["condition_code"]].append(i)
    rnd = random.Random(7)
    out = []
    while len(out) < n and any(by.values()):
        for code in sorted(by):
            if by[code] and len(out) < n:
                out.append(by[code].pop(rnd.randrange(len(by[code]))))
    return out


def main() -> None:
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 40
    rows = []
    for it in pick(n):
        st = PipelineState(query="what is wrong with this plant", image_bytes=base64.b64encode((IMG / it["file"]).read_bytes()).decode(), image_format="jpeg", image_name=it["file"])
        t0 = time.time()
        ok = caption.run(st)
        row = {"file": it["file"], "truth": it["condition_code"], "caption_ok": ok}
        if ok:
            retrieve.retrieve_images(st)
            caption.agree(st)
            va = st.visual_agreement or {}
            row.update({"judge_passed": st.caption_judge["passed"], "retried": st.caption_judge["retried"], "fixed": bool(st.caption_judge["fixed_fields"]), "leaked": st.caption_judge["leaked"],
                        "reference": va.get("reference_choice"), "caption_choice": va.get("caption_choice"), "status": va.get("status")})
        row["secs"] = round(time.time() - t0, 1)
        row["cost"] = round(st.total_cost_usd, 6)
        rows.append(row)
        print(f"{row['truth']:34s} ref={row.get('reference')} cap={row.get('caption_choice')} {row.get('status')}")
    ok = [r for r in rows if r["caption_ok"]]
    m = max(1, len(ok))
    acc = lambda sel, key: (sum(1 for r in sel if r.get(key) == r["truth"]), len(sel))  # noqa: E731
    ag = [r for r in ok if r.get("status") == "agree"]
    dis = [r for r in ok if r.get("status") == "disagree"]
    summary = {"photos": len(rows), "caption_produced": len(ok), "judge_passed": sum(1 for r in ok if r["judge_passed"]), "judge_rewrote_fields": sum(1 for r in ok if r["fixed"]),
               "second_caption_needed": sum(1 for r in ok if r["retried"]), "names_leaked_in_final": sum(1 for r in ok if r["leaked"]),
               "status_counts": dict(Counter(r.get("status") for r in ok)), "reference_match_correct": acc(ok, "reference"), "caption_choice_correct": acc(ok, "caption_choice"),
               "when_agree_reference_correct": acc(ag, "reference"), "when_disagree_reference_correct": acc(dis, "reference"), "when_disagree_caption_correct": acc(dis, "caption_choice"),
               "avg_secs": round(sum(r["secs"] for r in ok) / m, 1), "avg_cost_usd": round(sum(r["cost"] for r in ok) / m, 5)}
    print(json.dumps(summary, indent=1))
    (HERE / "caption_eval.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
