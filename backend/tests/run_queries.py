"""
run_queries.py — Runner for the test queries in data/queries.json.

For every query it sends the real request (including the holdout photo, if the spec has one), then checks
  * ROUTE   : route taken vs expected_route (reported separately, a route mismatch is a router finding)
  * CONTENT : the answer against the facts the dataset says must appear (stage, days, issue, rain, sources ...)
Usage: python tests/run_queries.py [--live] [--ids Q01,Q05]   (--live uses real Bedrock)
"""
from __future__ import annotations

import base64
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, pipeline
from app.schemas import AdvisoryRequest


def load_queries() -> list[dict]:
    with open(config.QUERIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _trace(result) -> list:
    obs = result.observability
    return list(getattr(obs, "trace", None) or []) if obs else []


def check_content(result, q: dict) -> list[str]:
    """Return failures. Checks are derived from q['facts'] (computed from the dataset), not from literal labels."""
    failures = []
    text = ((result.answer or "") + " " + " ".join(result.recommendations or [])
            + " " + " ".join(result.risks or []) + " " + " ".join(result.limitations or [])).lower()
    facts_all = q.get("facts") or {}
    f = next(iter(facts_all.values()), {}) if q.get("parcel_id") else facts_all

    def need(ok: bool, what: str):
        if not ok:
            failures.append(what)

    for kw in q.get("answer_must_contain") or []:
        if kw == "stage":
            need(f.get("stage", "x").split(" - ")[0].lower() in text, f"stage {f.get('stage')!r} not in answer")
        elif kw == "days_after_planting":
            need(str(f.get("days_after_planting")) in text, f"{f.get('days_after_planting')} days not in answer")
        elif kw == "issue":
            label = f.get("issue", "").lower()
            words = [w for w in re.findall(r"[a-z]+", label) if len(w) >= 3]
            need(label in text or (words and all(w in text for w in words)) or f.get("issue_code") == "healthy",
                 f"issue {f.get('issue')!r} not mentioned")
        elif kw == "zone":
            need(any(w in text for w in (f.get("zone", "?"), "waterlog", "drain")), "zone/waterlogging context missing")
        elif kw == "area_ha":
            need(str(f.get("area_ha")) in text, f"area {f.get('area_ha')} ha not in answer")
        elif kw == "days_since_irrigation":
            need(str(f.get("days_since_irrigation")) in text, "days since irrigation missing")
        elif kw == "days_since_fertilizer":
            need(str(f.get("days_since_fertilizer")) in text, "days since fertilizer missing")
        elif kw == "forecast_rain":
            need(bool(re.search(r"rain|mm|shower|forecast", text)), "no rain/forecast information")
        elif kw == "cited_source":
            need(bool(result.sources) or "tnau" in text, "no source cited")
        elif kw == "says_evidence_insufficient":
            need(bool(re.search(r"insufficient|not available|no (grounded )?(information|advice)|cannot|unable|limited", text)),
                 "does not say evidence is insufficient")
        elif kw == "refers_to_expert":
            need(bool(re.search(r"expert|kvk|extension|officer|agronomist|consult", text)), "does not refer to an expert")
        elif kw == "crop_mismatch_flagged":
            need(result.route == config.ROUTE_OUT_OF_SCOPE, f"expected OUT_OF_SCOPE, got {result.route!r}")
        elif kw == "marks_cached_data":
            tr = _trace(result)
            need("cached" in text or any(getattr(t, "status", "") == "fallback" or "cached" in str(getattr(t, "output_summary", "")).lower() for t in tr),
                 "weather fallback not marked as cached")
        elif kw == "count":
            need(str(f.get("rice_parcel_count")) in text, f"parcel count {f.get('rice_parcel_count')} missing")
        elif kw == "total_area_ha":
            area = f.get("rice_total_area_ha")
            need(f"{area:.1f}" in text or f"{area:.2f}" in text or str(int(area)) in text, f"total area {area} ha missing")
        elif kw == "crop":
            need((q.get("crop") or "rice").lower() in text or "paddy" in text, "crop not identified")
        else:
            need(kw.lower() in text, f"unknown check {kw!r}")
    return failures


def build_request(q: dict) -> AdvisoryRequest:
    kwargs = {"query": q["query"], "parcel_id": q.get("parcel_id")}
    if q.get("image"):
        p = config.DATA_DIR / q["image"]
        if p.exists():
            kwargs.update(image_bytes=base64.b64encode(p.read_bytes()).decode(), image_format="jpeg", image_name=p.name)
        else:
            print(f"  WARNING: image missing for {q['id']}: {p}")
    return AdvisoryRequest(**kwargs)


def main():
    live_mode = "--live" in sys.argv
    only = None
    if "--ids" in sys.argv:
        only = set(sys.argv[sys.argv.index("--ids") + 1].split(","))
    queries = [q for q in load_queries() if not only or q["id"] in only]

    if not live_mode:
        import numpy as np
        import app.models.bedrock as bm

        bm.invoke_text = lambda *a, **kw: ("Advisory generated. (dummy data)", 100, 50.0)

        def _mock_embed(text):
            np.random.seed(abs(hash(text[:32])) % (2**31))
            v = np.random.randn(256).astype(np.float32)
            return (v / np.linalg.norm(v)).tolist()

        bm.embed_text = _mock_embed
        bm.embed_image = lambda b: [0.1] * 1024

    print(f"\nCropsy Query Runner — {len(queries)} queries  mode={'LIVE' if live_mode else 'MOCK'}")
    print("=" * 96)

    rows = []
    for q in queries:
        t0 = time.perf_counter()
        try:
            result = pipeline.run(build_request(q), inject_failure=q.get("inject_failure"))
            ms = (time.perf_counter() - t0) * 1000
            route_ok = result.route == q["expected_route"]
            issues = check_content(result, q)
            v = result.verification
            rows.append({"id": q["id"], "route": result.route, "expected_route": q["expected_route"], "route_ok": route_ok,
                         "content_ok": not issues, "issues": issues, "verification": v.status if v else "?",
                         "latency_ms": round(ms), "cost_usd": result.estimated_cost_usd or 0,
                         "model": result.model_selected, "answer": (result.answer or "")[:240]})
            r = rows[-1]
            print(f"  {'ok ' if r['content_ok'] else 'BAD'} content | {'ok ' if route_ok else 'BAD'} route  {q['id']}  "
                  f"{result.route:13s} (exp {q['expected_route']:12s}) {r['verification']:8s} {ms:6.0f}ms"
                  + ("  <- " + "; ".join(issues) if issues else ""))
        except Exception as e:
            import traceback; traceback.print_exc()
            rows.append({"id": q["id"], "route_ok": False, "content_ok": False, "issues": [f"ERROR {e}"]})
            print(f"  ERROR {q['id']}: {e}")

    n = len(rows)
    print("=" * 96)
    print(f"CONTENT correct: {sum(r['content_ok'] for r in rows)}/{n}   ROUTE as expected: {sum(r['route_ok'] for r in rows)}/{n}   "
          f"both: {sum(r['content_ok'] and r['route_ok'] for r in rows)}/{n}")
    print(f"total cost ${sum(r.get('cost_usd', 0) for r in rows):.4f}   mean latency {sum(r.get('latency_ms', 0) for r in rows) / max(n, 1):.0f} ms")

    out = Path(__file__).parent / "query_results.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results written to {out}")


if __name__ == "__main__":
    main()
