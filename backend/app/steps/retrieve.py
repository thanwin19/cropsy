"""
retrieve.py — Step 5: Semantic retrieval from knowledge chunks (Titan Text V2)
             and optional image matching (Titan Multimodal).
Uses pre-built embedding cache when available; falls back to cosine over raw text.
"""
from __future__ import annotations

import json
import os
import re
import logging
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from app import config
from app.models import bedrock
from app.schemas import PipelineState, TraceEntry
from app.steps import hybrid

log = logging.getLogger(__name__)

# ── Chunk store ───────────────────────────────────────────────────────────────
MULTIVEC = os.getenv("CROPSY_MULTIVEC", "1") == "1"
_CHUNKS: list[dict] = []
_CHUNK_EMBEDDINGS: np.ndarray | None = None   # shape (N, 256)

# ── Image manifest ────────────────────────────────────────────────────────────
_MANIFEST: dict[str, dict] = {}
_IMAGE_EMBEDDINGS: np.ndarray | None = None
_IMAGE_KEYS: list[str] = []


_CTL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_GARBLED: list[int] = []      # rows whose text is mostly control characters (a PDF with a broken font encoding): kept in the file so row order and embeddings stay aligned, never retrieved


def _quarantine_garbled() -> None:
    """Mark unreadable chunks (more than 5% control characters) so they are never ranked, and strip stray control characters from the rest."""
    _GARBLED.clear()
    for i, c in enumerate(_CHUNKS):
        t = c.get("text") or ""
        if len(_CTL.findall(t)) / max(1, len(t)) > 0.05:
            _GARBLED.append(i)
        else:
            c["text"] = _CTL.sub(" ", t)


_SUB: dict | None = None      # finer index: one embedding per ~250-character window, each pointing at its parent chunk (scripts/embed_subchunks.py)


def _load_sub() -> None:
    global _SUB
    if _SUB is not None:
        return
    f = config.CACHE_DIR / "subchunks.npz"
    if f.exists() and MULTIVEC:
        z = np.load(f)
        _SUB = {"emb": z["emb"].astype(np.float32), "parent": z["parent"].astype(np.int64)}


_REGION_CACHE: dict = {}


def _region_adjust(state: PipelineState) -> np.ndarray:
    """A small bonus for chunks that apply to the farmer's region (+0.02 same zone, +0.01 same state) and a small penalty for chunks from another region (-0.08). It re-orders; it never removes a chunk,
    and nothing happens when the farmer's region is unknown. relevance_score stays the plain similarity."""
    from app import region as _region
    r = state.region or {}
    adj = np.zeros(len(_CHUNKS), dtype=np.float32)
    if not (r.get("state") or r.get("country")):
        return adj
    key = (r.get("state"), r.get("zone"), r.get("country"), len(_CHUNKS))
    if key not in _REGION_CACHE:
        vals = np.zeros(len(_CHUNKS), dtype=np.float32)
        for i, c in enumerate(_CHUNKS):
            m = _region.match(r, c)
            vals[i] = {"zone": 0.02, "state": 0.01, "country": 0.0, "mismatch": -0.08, "unknown": 0.0}[m]
        _REGION_CACHE[key] = vals
    return _REGION_CACHE[key]


def _load_chunks():
    global _CHUNKS
    if _CHUNKS:
        return
    f = config.CHUNKS_FILE
    if not f.exists():
        log.warning("chunks.jsonl not found: %s", f)
        return
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                _CHUNKS.append(json.loads(line))
    _quarantine_garbled()
    log.info("Loaded %d knowledge chunks", len(_CHUNKS))


def _load_embeddings():
    global _CHUNK_EMBEDDINGS
    if _CHUNK_EMBEDDINGS is not None:
        return
    f = config.EMBED_CACHE_FILE
    if f.exists():
        data = np.load(f, allow_pickle=False)
        _CHUNK_EMBEDDINGS = data["embeddings"]
        log.info("Loaded chunk embeddings from cache: shape=%s", _CHUNK_EMBEDDINGS.shape)
    else:
        log.warning("Embedding cache not found at %s — will use BM25 fallback", f)


def _manifest_by_file(raw):
    """The manifest is {count, per_class, items: [{file, ...}]}; return {file: meta}."""
    items = raw.get("items", raw) if isinstance(raw, dict) else raw
    return {it["file"]: it for it in items} if isinstance(items, list) else items


def _load_manifest():
    global _MANIFEST
    if _MANIFEST:
        return
    f = config.IMAGE_MANIFEST_FILE
    if not f.exists():
        return
    with open(f, encoding="utf-8") as fh:
        _MANIFEST = _manifest_by_file(json.load(fh))
    log.info("Loaded image manifest: %d entries", len(_MANIFEST))


def _load_image_embeddings():
    global _IMAGE_EMBEDDINGS, _IMAGE_KEYS
    if _IMAGE_EMBEDDINGS is not None:
        return
    f = config.IMAGE_EMBED_CACHE_FILE
    if not f.exists():
        return
    data = np.load(f, allow_pickle=True)
    _IMAGE_EMBEDDINGS = data["embeddings"]
    _IMAGE_KEYS = list(data["keys"])
    log.info("Loaded image embeddings: %d", len(_IMAGE_KEYS))


# ── Cosine similarity ─────────────────────────────────────────────────────────
def _cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Dot product of normalised vectors (row-wise)."""
    a_norm = a / (np.linalg.norm(a) + 1e-9)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return b_norm @ a_norm


# ── BM25 fallback (term frequency only, no IDF, fast) ────────────────────────
def _bm25_score(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    tokens = set(query.lower().split())
    scored = []
    for c in chunks:
        text = (c.get("text") or "").lower()
        score = sum(text.count(t) for t in tokens)
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


# ── Crop filter ───────────────────────────────────────────────────────────────
def _crop_filtered(chunks: list[dict], crop_hint: str | None) -> list[dict]:
    if not crop_hint:
        return chunks
    crop_lc = config.norm_crop(crop_hint)
    preferred = [c for c in chunks if crop_lc in (c.get("crop") or "").lower()]
    if crop_lc in {c.lower() for c in config.CROPS} and len(preferred) >= 2:
        return preferred                      # the question names a covered crop and its own passages answer it: another crop's passages are not mixed in (a wheat question gets no sesame advice)
    rest = [c for c in chunks if c not in preferred]
    return preferred + rest


# ── Text retrieval ────────────────────────────────────────────────────────────
def retrieve_chunks(state: PipelineState) -> PipelineState:
    _load_chunks()
    _load_embeddings()

    t0 = time.perf_counter()
    query = state.normalized_query or state.query
    if state.visual_caption:          # a photo question: add what the photo shows (appearance only) to the search text
        from app.steps import caption as _cap
        query = f"{query}. Photo shows: {_cap.summary(state.visual_caption)}"
    ms = [m for m in (state.image_matches or []) if m.get("condition")]
    if ms:                            # the nearest reference photos name a condition: search the guides for it too, so the answer is checked against real evidence for that condition
        query = f"{query}. Reference photos match: {ms[0].get('crop') or ''} {ms[0].get('condition')}"
    top_k = config.MAX_CHUNKS
    titan_invoked = False

    if _CHUNK_EMBEDDINGS is not None and _CHUNKS:
        # Titan Text V2 embedding
        try:
            from app.models import bedrock
            q_vec = np.array(bedrock.embed_text(query), dtype=np.float32)
            scores = _cosine(q_vec, _CHUNK_EMBEDDINGS.astype(np.float32))
            _load_sub()
            if _SUB is not None:                      # multi-vector: a chunk scores as well as its best ~250-character window
                best = np.full(len(_CHUNKS), -1.0, dtype=np.float32)
                np.maximum.at(best, _SUB["parent"], _cosine(q_vec, _SUB["emb"]).astype(np.float32))
                scores = np.maximum(scores, best)
            if _GARBLED:
                scores[_GARBLED] = -1.0
            rank_scores = scores + _region_adjust(state) + hybrid.term_bonus(query, _CHUNKS)
            crop_lc = config.norm_crop(state.crop_hint or "") if state.crop_hint else ""
            if crop_lc and crop_lc in {c.lower() for c in config.CROPS}:      # the question is about a covered crop: that crop's passages come first, so another crop's spacing or dose line cannot take its place
                rank_scores = rank_scores + 0.30 * np.array([(c.get("crop") or "").lower() == crop_lc for c in _CHUNKS], dtype=np.float32)
            if hybrid.ENABLED:       # keyword search + dense search fused, then a light rerank (no model call); the cosine score is kept for the sufficiency test
                top_idx = np.argsort(-hybrid.fuse(query, _CHUNKS, rank_scores))[:top_k * 3]
            else:
                top_idx = np.argsort(-rank_scores)[:top_k * 3]  # over-fetch, then filter
            candidates = [dict(_CHUNKS[i], relevance_score=float(scores[i])) for i in top_idx]
            titan_invoked = True
        except Exception as e:
            log.warning("Titan embed_text failed: %s — BM25 fallback", e)
            candidates = _bm25_score(query, _CHUNKS, top_k * 3)
            for c in candidates:
                c.setdefault("relevance_score", 0.5)
    else:
        candidates = _bm25_score(query, _CHUNKS, top_k * 3)
        for c in candidates:
            c.setdefault("relevance_score", 0.5)

    # Crop filter: push crop-matching chunks to top
    candidates = _crop_filtered(candidates, state.crop_hint)

    # Parcel crop filter if parcel loaded
    if state.parcel_context:
        p_crop = (state.parcel_context.get("crop", {}) or {}).get("name", "")
        if p_crop:
            candidates = _crop_filtered(candidates, p_crop)

    state.chunks = candidates[:top_k]
    # No crop named, no parcel, no photo, and no strong match: the passages found belong to some arbitrary crop. Answer as labelled general guidance (which asks for the crop) instead of citing them.
    best = max((c.get("relevance_score") or 0 for c in state.chunks), default=0)
    hint = str(state.crop_hint or "").strip().lower()
    if not state.parcel_id and not state.parcel_context and not state.image_bytes and hint in ("", "null", "none", "general", "crop", "plant", "all") and (best < 0.65 or (best < 0.8 and len({c.get('crop') for c in state.chunks}) >= 3)) and not state.force_guide and not state.force_facts:
        state.force_general = True
    state.evidence_local_sufficient = len(state.chunks) >= 2 and any(
        (c.get("relevance_score") or 0) > 0.7 for c in state.chunks
    )
    state.evidence_gap_detected = not state.evidence_local_sufficient

    latency_ms = (time.perf_counter() - t0) * 1000
    cost = bedrock.est_cost(config.MODEL_TITAN_TEXT, 50 * len(query.split())) if titan_invoked else 0.0
    state.total_cost_usd += cost

    state.trace.append(TraceEntry(
        step="retrieve/text", tool_or_model=config.MODEL_TITAN_TEXT if titan_invoked else "bm25_fallback",
        why="Dense + keyword (BM25) retrieval fused by rank, light rerank, over TNAU knowledge chunks" if hybrid.ENABLED else "Dense semantic retrieval over TNAU knowledge chunks",
        status="ok", latency_ms=latency_ms, est_cost_usd=cost,
        input_summary=f"query={query[:60]} crop={state.crop_hint}",
        output_summary=f"chunks={len(state.chunks)} sufficient={state.evidence_local_sufficient}",
    ))
    return state


# ── Image retrieval ───────────────────────────────────────────────────────────
def _summarise_matches(state: PipelineState) -> None:
    """Condense the nearest reference photos into a consensus the model must use, and detect evidence gaps."""
    ms = [m for m in state.image_matches if m.get("condition_code")]
    if not ms:
        return
    votes: dict[str, list[float]] = {}
    for m in ms:
        votes.setdefault(m["condition_code"], []).append(m.get("similarity", 0.0))
    ranked = sorted(votes.items(), key=lambda kv: (-len(kv[1]), -sum(kv[1]) / len(kv[1])))
    top_code, sims = ranked[0]
    label = next(m.get("condition") for m in ms if m["condition_code"] == top_code)
    crop = next((m.get("crop") for m in ms if m["condition_code"] == top_code), "")
    state.image_consensus = (
        f"{len(sims)} of {len(ms)} nearest reference photos show {crop} - {label} "
        f"(mean similarity {sum(sims) / len(sims):.2f}); others: "
        + (", ".join(f"{c} x{len(s)}" for c, s in ranked[1:]) or "none")
    )
    # Photo evidence vs the parcel's recorded (dummy) issue: if they disagree, say so instead of blending them.
    rec = ((state.parcel_context or {}).get("observed_issue") or {})
    if rec.get("code") and rec["code"] != top_code and top_code != "field_scene":
        state.image_consensus += (
            f". CONFLICT: the parcel record lists {rec.get('label')!r}, which differs from the photo match. "
            "Report both, say the diagnosis is uncertain, and ask for a closer, well-lit photo of one affected leaf"
        )
        state.limitations = (state.limitations or []) + [
            f"Photo match ({label}) disagrees with the parcel record ({rec.get('label')}); diagnosis uncertain."
        ]
    if top_code in config.GAP_ISSUE_CODES and len(sims) >= 2:
        state.gap_condition = label
        state.route = config.ROUTE_INSUFFICIENT
        state.evidence_gap_detected = True


def retrieve_images(state: PipelineState) -> PipelineState:
    if not state.image_bytes:
        return state

    _load_manifest()
    _load_image_embeddings()

    if _IMAGE_EMBEDDINGS is None or not _IMAGE_KEYS:
        log.warning("Image embedding cache not available — skipping image retrieval")
        return state

    t0 = time.perf_counter()
    top_k = config.MAX_IMAGE_MATCHES

    try:
        q_vec = np.array(bedrock.embed_image(state.image_bytes), dtype=np.float32)
        scores = _cosine(q_vec, _IMAGE_EMBEDDINGS.astype(np.float32))
        top_idx = np.argsort(-scores)[:top_k]
        matches = []
        for i in top_idx:
            key = _IMAGE_KEYS[i]
            meta = _MANIFEST.get(key, {})
            # Only use train split
            if meta.get("split") == "holdout":
                continue
            matches.append({**meta, "similarity": float(scores[i]), "key": key})
        state.image_matches = matches
        _summarise_matches(state)
    except Exception as e:
        log.warning("Image retrieval failed: %s", e)

    latency_ms = (time.perf_counter() - t0) * 1000
    cost = config.COST_PER_1K.get(config.MODEL_TITAN_MULTIMODAL, 0.00006)
    state.total_cost_usd += cost

    state.trace.append(TraceEntry(
        step="retrieve/images", tool_or_model=config.MODEL_TITAN_MULTIMODAL,
        why="Match uploaded image against train-split image embeddings",
        status="ok", latency_ms=latency_ms, est_cost_usd=cost,
        input_summary=f"image={state.image_name}",
        output_summary=f"matches={len(state.image_matches)}",
    ))
    return state


# ── Evidence check ────────────────────────────────────────────────────────────
def evidence_check(state: PipelineState) -> PipelineState:
    """Verify we have enough chunks; add limitation if gap detected."""
    if state.evidence_gap_detected:
        state.limitations = state.limitations or []
        state.limitations.append(
            "Insufficient evidence in knowledge base — recommendation may be incomplete. Confirm with your local KVK."
        )
    return state


# ── Main entry ────────────────────────────────────────────────────────────────
def run(state: PipelineState) -> PipelineState:
    state = retrieve_images(state)        # photo matches first: the text search then looks for what the nearest reference photos show
    state = retrieve_chunks(state)
    state = evidence_check(state)
    return state
