"""embed_subchunks.py: a second, finer embedding index over the knowledge base ("multi-vector retrieval").

Why: a TNAU chunk is about 900 characters of mixed bullets (for example one stem-borer sentence inside a long pest-management list). One embedding for the whole chunk
dilutes that sentence, so a short question about it ranks the chunk low (measured: rice stem-borer pheromone traps, relevant chunk at rank 12 of the rice chunks).
Here every chunk is also cut into small windows (about 250 characters, split at bullet and sentence boundaries, each prefixed with the crop and section for context) and each window is embedded.
At query time a chunk's score is the better of its own cosine and its best window's cosine. The chunk file, its order and the existing embeddings are untouched.

Output: backend/cache/subchunks.npz  (emb: N x 256, parent: N parent row numbers) and backend/cache/subchunks.json (window texts, for inspection).
Resumable and cheap: about 4,000 Titan Text V2 calls, roughly $0.01. Usage: python scripts/embed_subchunks.py"""
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402
from app.models import bedrock  # noqa: E402

TARGET, MINLEN = 260, 60
CTL = re.compile("[" + chr(0) + "-" + chr(8) + chr(11) + chr(12) + chr(14) + "-" + chr(31) + chr(127) + "-" + chr(159) + "]")


def windows(text: str) -> list[str]:
    text = CTL.sub(" ", text)
    parts = [p.strip() for p in re.split(r"\n\s*[•\-\*]\s*|\n{2,}|(?<=[.;:])\s+(?=[A-Z•])", text) if p and p.strip()]
    out, buf = [], ""
    for p in parts:
        if buf and len(buf) + len(p) + 1 > TARGET:
            out.append(buf)
            buf = p
        else:
            buf = f"{buf} {p}".strip()
    if buf:
        out.append(buf)
    return [w for w in out if len(w) >= MINLEN] or ([text.strip()[:TARGET * 2]] if len(text.strip()) >= MINLEN else [])


def main() -> None:
    chunks = [json.loads(l) for l in open(config.CHUNKS_FILE, encoding="utf-8") if l.strip()]
    items = []
    for i, c in enumerate(chunks):
        head = f"{c['crop']}" + (f" - {c['section']}" if c.get("section") and len(str(c["section"])) < 60 and "::" not in str(c["section"]) else "")
        for w in windows(c["text"]):
            items.append((i, f"{head}: {w}"))
    FACT = re.compile(r"(seed rate|spacing|sowing time|ideal sowing|seed requirement)[:\s\-]*[\s\S]{0,120}", re.IGNORECASE)      # a short fact tucked at the end of a long table chunk gets its own small window
    have = {t for _p, t in items}
    for i, c in enumerate(chunks):
        for m in FACT.finditer(CTL.sub(" ", c["text"])):
            t = f"{c['crop']} " + re.sub(r"\s+", " ", m.group(0)).strip()
            if len(t) >= 24 and t not in have:
                have.add(t)
                items.append((i, t))
    print(f"{len(chunks)} chunks -> {len(items)} windows")
    out_npz, out_json = config.CACHE_DIR / "subchunks.npz", config.CACHE_DIR / "subchunks.json"
    done = []
    if out_npz.exists() and out_json.exists():
        old = json.loads(out_json.read_text(encoding="utf-8"))
        if [t for _p, t in items][:len(old["texts"])] == old["texts"]:
            done = list(np.load(out_npz)["emb"])
            print(f"resuming from {len(done)} cached windows")
    t0 = time.time()
    for k in range(len(done), len(items)):
        for attempt in range(4):
            try:
                done.append(np.array(bedrock.embed_text(items[k][1]), dtype=np.float32))
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
        if (k + 1) % 400 == 0:
            np.savez(out_npz, emb=np.stack(done), parent=np.array([p for p, _t in items[:len(done)]]))
            out_json.write_text(json.dumps({"texts": [t for _p, t in items]}, ensure_ascii=False), encoding="utf-8")
            print(f"  {k + 1}/{len(items)} ({time.time() - t0:.0f}s)")
    np.savez(out_npz, emb=np.stack(done), parent=np.array([p for p, _t in items]))
    out_json.write_text(json.dumps({"texts": [t for _p, t in items]}, ensure_ascii=False), encoding="utf-8")
    print(f"done: {len(done)} windows saved to {out_npz}")


if __name__ == "__main__":
    main()
