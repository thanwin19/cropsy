"""Evaluate Titan Multimodal nearest-neighbour matching on the HOLDOUT photos (never in the reference index).

For every holdout image: embed it, find the k nearest train/reference photos, majority-vote the condition.
Reports condition accuracy overall and per class, with and without restricting the search to the parcel's crop
(the pipeline knows the crop from the parcel, so the restricted number is the realistic one for parcel questions).
Embeddings are cached in backend/cache/holdout_embeddings.npz, so reruns cost nothing.
Run: python backend/scripts/eval_image_retrieval.py
"""
import base64
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config
from app.models import bedrock

K = 3
CACHE = config.CACHE_DIR / "holdout_embeddings.npz"


def main():
    raw = json.loads(config.IMAGE_MANIFEST_FILE.read_text(encoding="utf-8"))
    items = {it["file"]: it for it in raw["items"]}
    ref = np.load(config.IMAGE_EMBED_CACHE_FILE, allow_pickle=True)
    ref_keys, ref_emb = list(ref["keys"]), ref["embeddings"].astype(np.float32)
    ref_emb /= np.linalg.norm(ref_emb, axis=1, keepdims=True)
    ref_crop = np.array([items[k]["crop"] for k in ref_keys])
    ref_cond = np.array([items[k]["condition_code"] for k in ref_keys])

    hold = [it for it in items.values() if it["split"] == "holdout"]
    cache = {}
    if CACHE.exists():
        d = np.load(CACHE, allow_pickle=True)
        cache = dict(zip(d["keys"], d["emb"]))
    for i, it in enumerate(hold):
        if it["file"] in cache:
            continue
        b64 = base64.b64encode((config.DATA_DIR / "images" / it["file"]).read_bytes()).decode()
        cache[it["file"]] = np.array(bedrock.embed_image(b64), dtype=np.float32)
        if i % 25 == 0:
            print(f"  embedded {i}/{len(hold)}", flush=True)
    np.savez_compressed(CACHE, keys=np.array(list(cache), dtype=object), emb=np.array(list(cache.values()), dtype=np.float32))

    def predict(vec, crop=None):
        v = vec / np.linalg.norm(vec)
        sims = ref_emb @ v
        if crop:
            sims = np.where(ref_crop == crop, sims, -1)
        top = np.argsort(-sims)[:K]
        votes = Counter(ref_cond[top])
        best = max(votes.items(), key=lambda kv: (kv[1], sum(sims[j] for j in top if ref_cond[j] == kv[0])))
        return best[0]

    rows = defaultdict(lambda: [0, 0, 0])  # n, ok_any_crop, ok_crop_restricted
    for it in hold:
        v = cache[it["file"]]
        key = f"{it['crop']}/{it['condition_code']}"
        rows[key][0] += 1
        rows[key][1] += predict(v) == it["condition_code"]
        rows[key][2] += predict(v, it["crop"]) == it["condition_code"]
    n = sum(r[0] for r in rows.values())
    a = sum(r[1] for r in rows.values())
    b = sum(r[2] for r in rows.values())
    print(f"\nHoldout photos: {n}   k={K}")
    print(f"condition accuracy, search all crops : {a}/{n} = {a / n:.1%}")
    print(f"condition accuracy, crop-restricted   : {b}/{n} = {b / n:.1%}\n")
    print(f"{'class':38s} n   all  crop")
    for k, (m, x, y) in sorted(rows.items()):
        print(f"{k:38s} {m:<3d} {x:<4d} {y:<4d}")


if __name__ == "__main__":
    main()
