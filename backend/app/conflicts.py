"""conflicts.py: recommendations in the knowledge base that differ between passages (data/knowledge_conflicts.json).
When the passages of a recorded conflict are retrieved together, the difference is shown to the farmer in the answer's limitations. Cropsy never picks one silently."""
from __future__ import annotations

import json
from functools import lru_cache

from app import config
from app.schemas import PipelineState


@lru_cache(maxsize=1)
def register() -> list[dict]:
    f = config.DATA_DIR / "knowledge_conflicts.json"
    return json.loads(f.read_text(encoding="utf-8"))["conflicts"] if f.exists() else []


def annotate(state: PipelineState) -> PipelineState:
    ids = {c.get("chunk_id") for c in (state.chunks or [])}
    for c in register():
        hit = [i for i in c["items"] if i["chunk_id"] in ids]
        if len(hit) >= 2:
            parts = "; ".join(f"{i['source']} (p. {i['page']}, {i['region']}): {i['claim']}" for i in hit)
            state.limitations = (state.limitations or []) + [f"Sources differ on {c['topic']} for {c['crop'].lower()}: {parts}. Cropsy does not choose between them: confirm with your KVK. Status: {c['status']}."]
    return state
