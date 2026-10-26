"""
embed_images.py — Build Titan Multimodal embeddings for train-split images.
Resumable: skips images already in cache.
Output: backend/cache/image_embeddings.npz  (embeddings + keys arrays)
Usage: python scripts/embed_images.py
"""
import base64
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.models import bedrock


def _load_image_b64(path: str) -> str:
    p = Path(path)
    if not p.exists():
        # Try relative to data/images
        p = config.DATA_DIR / "images" / path
    if not p.exists():
        raise FileNotFoundError(path)
    return base64.b64encode(p.read_bytes()).decode()


def main():
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not config.IMAGE_MANIFEST_FILE.exists():
        print(f"ERROR: manifest not found at {config.IMAGE_MANIFEST_FILE}")
        sys.exit(1)

    with open(config.IMAGE_MANIFEST_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    # The manifest is {count, per_class, items: [{file, split, ...}]}; index it by file path.
    items = raw.get("items", raw) if isinstance(raw, dict) else raw
    manifest = {it["file"]: it for it in items} if isinstance(items, list) else items

    # Only train split
    train_items = {k: v for k, v in manifest.items() if v.get("split") != "holdout"}
    print(f"Train images: {len(train_items)} / {len(manifest)} total")

    cache_file = config.IMAGE_EMBED_CACHE_FILE
    existing_keys: list[str] = []
    existing_embeddings: list = []
    if cache_file.exists():
        data = np.load(cache_file, allow_pickle=True)
        existing_keys = list(data["keys"])
        existing_embeddings = list(data["embeddings"])
        print(f"Resuming from {len(existing_keys)} cached image embeddings")

    done_set = set(existing_keys)
    keys = existing_keys[:]
    embeddings = existing_embeddings[:]
    failed = 0

    for i, (key, meta) in enumerate(train_items.items()):
        if key in done_set:
            continue
        img_path = meta.get("path") or key
        try:
            b64 = _load_image_b64(img_path)
            vec = bedrock.embed_image(b64)
            keys.append(key)
            embeddings.append(vec)
            done_set.add(key)
            if len(keys) % 20 == 0:
                _save(cache_file, keys, embeddings)
                print(f"  [{len(keys)}/{len(train_items)}] checkpoint saved")
            time.sleep(0.1)
        except FileNotFoundError:
            print(f"  SKIP (file not found): {img_path}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {key}: {e}")
            failed += 1

    _save(cache_file, keys, embeddings)
    print(f"Done. {len(keys)} image embeddings saved to {cache_file}  failed={failed}")


def _save(path: Path, keys: list, embeddings: list):
    np.savez_compressed(
        path,
        embeddings=np.array(embeddings, dtype=np.float32),
        keys=np.array(keys, dtype=object),
    )


if __name__ == "__main__":
    main()
