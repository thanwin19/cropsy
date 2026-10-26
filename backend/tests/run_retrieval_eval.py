"""run_retrieval_eval.py: score Cropsy's retrieval and its answer/abstain/clarify policy against tests/retrieval_eval.json.

What it measures (no language model; repeatable):
  retrieval   for answerable questions: hit@1, hit@3, hit@5 and MRR (a chunk is relevant only if it is from the right crop AND matches every evidence regex),
              crop precision@5 (share of the top 5 that are from an expected crop), and citation completeness (top hit carries a document id, a title and a page or section).
  policy      clarify questions must trigger the clarify gate; answerable questions must NOT be blocked by it; abstain questions are counted as handled when the
              router sends them to general guidance (a plant outside the covered crops) or when the best chunk is weak (relevance below 0.55).
Query embeddings are cached in tests/retrieval_query_embeddings.npz so a normal run needs no AWS. Use --refresh to embed new or changed questions with Titan (about $0.00002 each).
Modes: --hybrid scores the keyword-fused ranking instead of dense only.
Usage: python tests/run_retrieval_eval.py [--refresh] [--hybrid] [--json out.json]"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402,F401
from app.schemas import PipelineState  # noqa: E402
from app.steps import guides_dynamic, hybrid, retrieve, router  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "retrieval_eval.json"
DATA3 = HERE / "batchA_eval.json"             # Batch A: crops added from the TNAU guides, after approval
DATA2 = HERE / "universal_eval.json"       # the universal-agriculture part: more crop groups, regions, general-guidance and safety questions
CACHE = HERE / "retrieval_query_embeddings.npz"
WEAK = 0.55
BEFORE: dict = {}
MULTI = retrieve.MULTIVEC      # same default as the pipeline


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def load() -> list[dict]:
    qs = json.loads(DATA.read_text(encoding="utf-8"))["questions"]
    for extra in (DATA2, DATA3):
        if extra.exists():
            qs += json.loads(extra.read_text(encoding="utf-8"))["questions"]
    return qs


def embeddings(questions: list[dict], refresh: bool) -> dict[str, np.ndarray]:
    cache: dict[str, np.ndarray] = {}
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=False)
        cache = {k: z[k] for k in z.files}
    missing = [q for q in questions if _key(q["search_text"]) not in cache]
    if missing and refresh:
        from app.models import bedrock
        for q in missing:
            cache[_key(q["search_text"])] = np.array(bedrock.embed_text(q["search_text"]), dtype=np.float32)
        np.savez(CACHE, **cache)
    elif missing:
        raise SystemExit(f"{len(missing)} question(s) have no cached embedding; run with --refresh (needs AWS, about ${len(missing) * 0.00002:.5f}).")
    return cache


def relevant(chunk: dict, q: dict) -> bool:
    return chunk.get("crop") in q["crops"] and all(re.search(e, chunk.get("text", ""), re.I) for e in q["evidence"])


def rank(q: dict, vec: np.ndarray, use_hybrid: bool, mode: str = "pipeline") -> list[tuple[dict, float]]:
    """mode 'pipeline' = what retrieve.py does today (take the best 15 over ALL crops, then move the named crop to the front);
    mode 'crop_first' = rank only inside the named crop's chunks (the proposed change)."""
    retrieve._load_chunks()
    retrieve._load_embeddings()
    chunks, emb = retrieve._CHUNKS, retrieve._CHUNK_EMBEDDINGS.astype(np.float32)
    if BEFORE:                                       # score against an older knowledge base (same code, older chunks and embeddings)
        chunks, emb = BEFORE["chunks"], BEFORE["emb"]
    scores = retrieve._cosine(vec, emb)
    retrieve._load_sub()
    if MULTI and not BEFORE:                         # multi-vector: a chunk scores as well as its best small window (see scripts/embed_subchunks.py)
        child = retrieve._SUB
        if child is not None:
            cs = retrieve._cosine(vec, child["emb"])
            best = np.full(len(chunks), -1.0, dtype=np.float32)
            np.maximum.at(best, child["parent"], cs.astype(np.float32))
            scores = np.maximum(scores, best)
    if retrieve._GARBLED and not BEFORE:
        scores[retrieve._GARBLED] = -1.0           # unreadable chunks are never retrieved (same rule as retrieve.py)
    ranked = scores + hybrid.term_bonus(q["search_text"], chunks) if not BEFORE else scores
    if len(q["crops"]) == 1 and not BEFORE:
        ranked = ranked + 0.30 * np.array([c.get("crop") == q["crops"][0] for c in chunks], dtype=np.float32)      # same crop preference as retrieve.py      # same named-condition bonus as retrieve.py
    order = np.argsort(-hybrid.fuse(q["search_text"], chunks, scores)) if use_hybrid else np.argsort(-ranked)
    if mode == "crop_first" and len(q["crops"]) == 1:
        order = [i for i in order if chunks[i].get("crop") == q["crops"][0]]
        return [(chunks[i], float(scores[i])) for i in order[:5]]
    cand = [(chunks[i], float(scores[i])) for i in order[:config.MAX_CHUNKS * 3]]     # retrieve.py over-fetches top_k * 3 and then filters
    if len(q["crops"]) == 1:
        pref = [c for c in cand if c[0].get("crop") == q["crops"][0]]
        cand = pref if len(pref) >= 2 else pref + [c for c in cand if c not in pref]       # same rule as retrieve._crop_filtered
    return cand[:5]


def gate_blocks(q: dict) -> bool:
    """True if the not-understood gate would show the clarify card for this question (rules only, no model)."""
    # the live gate also sees what the understand step found (intent, crop); the dataset's own labels stand in for it here so the check stays offline
    st = PipelineState(query=q["question"], normalized_query=q["search_text"], intent=q.get("intent") or "general", crop_hint=(q["crops"][0] if len(q.get("crops", [])) == 1 else None))
    card = guides_dynamic.clarify_card(st)
    return bool(card and card.get("kind") == "clarify")


def goes_general(q: dict) -> bool:
    return bool(router._UNCOVERED_PLANTS.search(f"{q['question']} {q['search_text']}"))


def run(use_hybrid: bool = False, refresh: bool = False, mode: str = "pipeline") -> dict:
    qs = load()
    emb = embeddings(qs, refresh)
    res: dict = defaultdict(list)
    detail = []
    for q in qs:
        if q.get("live_only"):                                  # judged by the live pipeline (the answer step says the guide has no such line), not by retrieval scores
            continue
        row = {"id": q["id"], "lang": q["lang"], "policy": q["policy"]}
        if q["policy"] == "answer":
            top = rank(q, emb[_key(q["search_text"])], use_hybrid, mode)
            pos = next((i + 1 for i, (c, _s) in enumerate(top) if relevant(c, q)), None)
            row.update(first_relevant_rank=pos, top1=top[0][0]["chunk_id"], top1_score=round(top[0][1], 3))
            res["hit1"].append(pos == 1)
            res["hit3"].append(pos is not None and pos <= 3)
            res["hit5"].append(pos is not None)
            res["mrr"].append(1 / pos if pos else 0.0)
            res["crop_p5"].append(sum(c.get("crop") in q["crops"] for c, _s in top) / len(top))
            c0 = top[0][0]
            res["citation"].append(bool(c0.get("document_id") and c0.get("title") and (c0.get("page") or c0.get("section"))))
            res["not_blocked"].append(not gate_blocks(q))
            res[f"crop:{q['crops'][0]}:hit3"].append(pos is not None and pos <= 3)
            res[f"lang:{q['lang']}:hit3"].append(pos is not None and pos <= 3)
        elif q["policy"] == "general":                      # a crop or topic the knowledge base does not hold: offline we can only check the router's word list
            row["handled"] = goes_general(q)
            res["general_regex_ok"].append(row["handled"])
            res[f"grp:{q.get('group', '?')}:regex"].append(row["handled"])
        elif q["policy"] == "safety":
            from app import pesticides
            ok = any(n in q["banned"] for n, _k, _x in pesticides.mentioned(q["question"]))      # banned or restricted: either must be recognised
            row["handled"] = ok
            res["safety_detected"].append(ok)
        elif q["policy"] == "clarify":
            ok = gate_blocks(q)
            row["handled"] = ok
            res["clarify_ok"].append(ok)
        else:
            top = rank({**q, "crops": []}, emb[_key(q["search_text"])], use_hybrid)
            weak = top[0][1] < WEAK
            text = f"{q['question']} {q['search_text']}"
            from app.steps import guides_extra as gx
            card = bool(guides_dynamic.PRICE_RX.search(text) or gx.PEST_CHECK_RX.search(text))      # a price or pesticide-registry question gets a fixed "I do not hold this" card, no model answer
            ok = goes_general(q) or weak or card
            row.update(handled=ok, top1_score=round(top[0][1], 3), via="router: uncovered plant" if goes_general(q) else ("fixed card (price or pesticide registry)" if card else ("weak match" if weak else "NOT handled: a confident-looking chunk would be used")))
            res["abstain_ok"].append(ok)
        detail.append(row)

    def mean(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    return {"mode": ("hybrid" if use_hybrid else "dense") + ("+multivec" if MULTI else "") + "/" + mode, "n_questions": len(qs), "n_answerable": len(res["hit1"]),
            "hit@1": mean(res["hit1"]), "hit@3": mean(res["hit3"]), "hit@5": mean(res["hit5"]), "mrr": mean(res["mrr"]), "crop_precision@5": mean(res["crop_p5"]),
            "citation_complete": mean(res["citation"]), "answerable_not_blocked_by_gate": mean(res["not_blocked"]),
            "clarify_handled": mean(res["clarify_ok"]), "abstain_handled": mean(res["abstain_ok"]),
            "general_questions": len(res["general_regex_ok"]), "general_caught_by_word_list": mean(res["general_regex_ok"]), "safety_banned_name_detected": mean(res["safety_detected"]),
            "general_by_group_word_list": {k.split(":")[1]: mean(v) for k, v in res.items() if k.startswith("grp:")},
            "by_crop_hit@3": {k.split(":")[1]: mean(v) for k, v in res.items() if k.startswith("crop:")},
            "by_language_hit@3": {k.split(":")[1]: mean(v) for k, v in res.items() if k.startswith("lang:")},
            "misses": [d for d in detail if d["policy"] == "answer" and (d["first_relevant_rank"] is None or d["first_relevant_rank"] > 3)],
            "policy_misses": [d for d in detail if d["policy"] != "answer" and not d["handled"]], "detail": detail}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--hybrid", action="store_true")
    ap.add_argument("--crop-first", action="store_true", help="rank inside the named crop only")
    ap.add_argument("--before", action="store_true", help="score against the backed-up knowledge base from before the pest-page ingestion (859 chunks)")
    ap.add_argument("--no-multivec", action="store_true", help="score whole chunks only (the older behaviour)")
    ap.add_argument("--json")
    a = ap.parse_args()
    global MULTI
    MULTI = retrieve.MULTIVEC and not a.no_multivec
    if a.before:
        kd = Path(__file__).resolve().parent.parent
        BEFORE["chunks"] = [json.loads(l) for l in open(kd / "knowledge" / "chunks.jsonl.bak_before_pest_pages", encoding="utf-8") if l.strip()]
        BEFORE["emb"] = np.load(kd / "cache" / "embeddings.npz.bak_before_pest_pages")["embeddings"].astype(np.float32)
    r = run(a.hybrid, a.refresh, "crop_first" if a.crop_first else "pipeline")
    print(f"mode={r['mode']}  questions={r['n_questions']}  answerable={r['n_answerable']}")
    for k in ("hit@1", "hit@3", "hit@5", "mrr", "crop_precision@5", "citation_complete", "answerable_not_blocked_by_gate", "clarify_handled", "abstain_handled", "general_questions", "general_caught_by_word_list", "safety_banned_name_detected"):
        print(f"  {k:32s} {r[k]}")
    print("  general questions by group, caught by the router's WORD LIST (the live router also uses the model's crop guess):", r["general_by_group_word_list"])
    print("  by crop hit@3:", r["by_crop_hit@3"])
    print("  by language hit@3:", r["by_language_hit@3"])
    for m in r["misses"]:
        print("  MISS", m["id"], "first relevant rank:", m["first_relevant_rank"], "top1:", m["top1"])
    for m in r["policy_misses"]:
        print("  POLICY", m["id"], m.get("via", "gate did not block"))
    if a.json:
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
