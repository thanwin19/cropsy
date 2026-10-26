"""knowledge_info.py: what the advisory documents (the RAG knowledge base) cover, how deeply, and what is missing, computed from the real chunk file."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from app import config

TOPIC_LABEL = {"variety_season": "varieties and season", "climate_soil": "climate and soil", "nursery_seed": "nursery and seed", "planting": "planting",
               "nutrient": "fertilizer and nutrients", "irrigation": "irrigation", "weed": "weeds", "pest": "pests", "disease": "diseases", "harvest": "harvest and storage"}
GOOD, FAIR = 60, 30
_cache: dict = {}


def summary() -> dict:
    if _cache:
        return _cache
    crops: Counter = Counter()
    topics: dict[str, Counter] = defaultdict(Counter)
    docs: Counter = Counter()
    try:
        for line in open(config.CHUNKS_FILE, encoding="utf-8"):
            c = json.loads(line)
            crops[c["crop"]] += 1
            docs[c["document_id"]] += 1
            for t in c.get("topics") or []:
                topics[c["crop"]][t] += 1
    except Exception:  # noqa: BLE001
        pass
    try:
        sources = json.loads((config.KNOWLEDGE_DIR / "sources.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        sources = []
    rows = []
    for crop in config.CROPS:
        n = crops.get(crop, 0)
        missing = [TOPIC_LABEL[t] for t in TOPIC_LABEL if topics[crop].get(t, 0) == 0]
        rows.append({"crop": crop, "passages": n, "depth": "good" if n >= GOOD else "fair" if n >= FAIR else "thin", "missing_topics": missing})
    try:
        built = datetime.fromtimestamp(config.CHUNKS_FILE.stat().st_mtime, tz=timezone.utc).date().isoformat()
    except Exception:  # noqa: BLE001
        built = None
    _cache.update({"built": built, "total_passages": sum(crops.values()), "crops": rows,
                   "sources": [{**s, "passages": docs.get(s.get("document_id"), 0)} for s in sources],
                   "not_covered": ["Trees and plants outside the 10 crops (for example neem): general guidance only, labelled as such.",
                                   "Live market prices, pesticide registration status, and farm-level soil or weather sensors.",
                                   "Tamil-language TNAU documents: all documents are English; Tamil questions are answered from them."]})
    return _cache


def depth_of(crop: str | None) -> str | None:
    if not crop:
        return None
    for r in summary()["crops"]:
        if r["crop"].lower() == crop.lower():
            return r["depth"]
    return None
