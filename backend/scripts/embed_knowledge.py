"""
embed_knowledge.py — Build Titan Text V2 embeddings for all knowledge chunks.
Resumable: skips chunks already in cache.
Output: backend/cache/embeddings.npz  (shape N×256)
Usage: python scripts/embed_knowledge.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.models import bedrock


def main():
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Load chunks
    if not config.CHUNKS_FILE.exists():
        print(f"ERROR: {config.CHUNKS_FILE} not found")
        sys.exit(1)

    chunks = []
    with open(config.CHUNKS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    print(f"Loaded {len(chunks)} chunks")

    # Load existing cache
    cache_file = config.EMBED_CACHE_FILE
    if cache_file.exists():
        data = np.load(cache_file, allow_pickle=False)
        existing = data["embeddings"]
        n_existing = existing.shape[0]
        print(f"Resuming from {n_existing} cached embeddings")
    else:
        existing = None
        n_existing = 0

    chunks_to_embed = chunks[n_existing:]
    if not chunks_to_embed:
        print("All chunks already embedded.")
        return

    embeddings = list(existing) if existing is not None else []
    failed = 0

    for i, chunk in enumerate(chunks_to_embed):
        text = chunk.get("text", "")
        try:
            vec = bedrock.embed_text(text[:8000])
            embeddings.append(vec)
            if (i + 1) % 10 == 0:
                # Save checkpoint
                np.savez_compressed(cache_file, embeddings=np.array(embeddings, dtype=np.float32))
                print(f"  [{n_existing + i + 1}/{len(chunks)}] saved checkpoint")
            time.sleep(0.05)   # avoid throttle
        except Exception as e:
            print(f"  ERROR chunk {n_existing + i}: {e}")
            embeddings.append([0.0] * 256)
            failed += 1

    np.savez_compressed(cache_file, embeddings=np.array(embeddings, dtype=np.float32))
    print(f"Done. Embeddings shape: {np.array(embeddings).shape}  failed={failed}")
    print(f"Saved to {cache_file}")


if __name__ == "__main__":
    main()
