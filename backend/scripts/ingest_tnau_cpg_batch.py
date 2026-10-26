"""Batch A: more crops from the two TNAU Crop Production Guides (2020) that are already in the repository (dataset/knowledge/TNAU_CPG). Same publisher, documents and chunker as the ten
crops already built; only the page ranges are new. Staged so that every stage can be measured before the next:

  stage 1  sorghum, pearl millet (cumbu), finger millet (ragi), wheat       (Agriculture guide)
  stage 2  redgram, greengram, cowpea, horsegram, bengalgram                (Agriculture guide)
  stage 3  tomato                                                           (Horticulture guide, pages 71-76)
  stage 4  soybean (185-189), sesame (209-216)                              (Agriculture guide)
  stage 5  castor (217-226), sunflower (227-234)                            (Agriculture guide)

Rules: APPENDS only (existing rows keep their position, so existing embeddings stay valid); a document+crop already present is skipped; a new chunk whose word-shingles are 80% or more
contained in an existing chunk of the same crop is dropped and reported; chunks with more than 5% control characters are dropped and reported. Every chunk keeps document id, title, page and
a region field (Tamil Nadu). Doses are as printed in the guide; none is invented or checked against a pesticide registry.
Usage: python scripts/ingest_tnau_cpg_batch.py --stage 1 [--dry-run]    then embed_knowledge.py and embed_subchunks.py"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_knowledge as bk  # noqa: E402

AG, HORT = bk.AG, bk.HORT
STAGES = {
    1: {"Sorghum": [(AG, 77, 92)], "Cumbu": [(AG, 93, 103)], "Ragi": [(AG, 104, 114)], "Wheat": [(AG, 134, 136)]},
    2: {"Redgram": [(AG, 137, 145)], "Greengram": [(AG, 156, 164)], "Cowpea": [(AG, 165, 169)], "Horsegram": [(AG, 170, 172)], "Bengalgram": [(AG, 173, 184)]},
    3: {"Tomato": [(HORT, 71, 76)]},
    4: {"Soybean": [(AG, 185, 189)], "Sesame": [(AG, 209, 216)]},
    5: {"Castor": [(AG, 217, 226)], "Sunflower": [(AG, 227, 234)]},
}
GENERIC_STAGES = ["germination", "seedling", "vegetative", "tillering", "flowering", "pod", "grain filling", "maturity", "harvest"]
REGION = {"country": "India", "state": "Tamil Nadu", "applies_to": "Tamil Nadu agro-ecological zones as named in the guide"}
CTL = re.compile("[" + chr(0) + "-" + chr(8) + chr(11) + chr(12) + chr(14) + "-" + chr(31) + chr(127) + "-" + chr(159) + "]")


def shingles(t, n=5):
    w = re.findall(r"[a-z0-9]+", t.lower())
    return {" ".join(w[i:i + n]) for i in range(max(1, len(w) - n + 1))}


def contained(a, b):
    sa = shingles(a)
    return len(sa & shingles(b)) / max(1, len(sa))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sections = STAGES[a.stage]
    pages = {}
    for line in open(bk.PAGES, encoding="utf-8"):
        p = json.loads(line)
        pages[(p["file"], p["page"])] = p
    for crop in sections:
        bk.STAGE_WORDS.setdefault(crop, GENERIC_STAGES)
    out = bk.OUT / "chunks.jsonl"
    existing = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
    new = []
    bk.build_sections(sections, pages, new)
    kept, dropped = [], []
    present = {(c["crop"], c["document_id"], c["page"]) for c in existing}
    for c in new:
        same = [e["text"] for e in existing if e["crop"] == c["crop"]]
        worst = max((contained(c["text"], t) for t in same), default=0.0)
        garbled = len(CTL.findall(c["text"])) / max(1, len(c["text"])) > 0.05
        if worst >= 0.8 or garbled or (c["crop"], c["document_id"], c["page"]) in present:
            dropped.append((c["chunk_id"], "duplicate" if worst >= 0.8 else "garbled" if garbled else "already ingested", round(worst, 2)))
            continue
        c["text"] = CTL.sub(" ", c["text"])
        c["region"] = REGION
        kept.append(c)
    print(f"stage {a.stage}: {len(new)} chunks built, {len(kept)} kept, {len(dropped)} dropped {dropped[:6]}")
    by = {}
    for c in kept:
        by.setdefault(c["crop"], []).append(c)
    for crop, cs in by.items():
        pg = sorted({c["page"] for c in cs})
        topics = {}
        for c in cs:
            for t in c["topics"][:1]:
                topics[t] = topics.get(t, 0) + 1
        print(f"  {crop:11s} {len(cs):3d} chunks  pages {pg[0]}-{pg[-1]}  with dose {sum(c['has_dose'] for c in cs)}  first topics {topics}")
    if a.dry_run:
        for c in kept[:3]:
            print("   sample:", c["chunk_id"], repr(c["text"][:150]))
        return
    with open(out, "a", encoding="utf-8") as f:
        for c in kept:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"appended {len(kept)} chunks ({len(existing)} -> {len(existing) + len(kept)}). Next: embed_knowledge.py, embed_subchunks.py")


if __name__ == "__main__":
    main()
