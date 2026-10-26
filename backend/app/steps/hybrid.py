"""hybrid.py: keyword (BM25) search fused with the dense (Titan) search, plus a light rerank. No model call, so no extra AWS cost.

Why: dense search misses exact terms (a disease name, 'sigatoka', a product or a number) and keyword search misses paraphrase; fusing the two ranks
fixes both. The cosine score of the dense search is still what the sufficiency test uses, so this only changes the ORDER of candidates.
Switch off with CROPSY_HYBRID=0 (retrieve.py then falls back to dense only)."""
from __future__ import annotations

import math
import os
import re
from collections import Counter

import numpy as np

ENABLED = os.getenv("CROPSY_HYBRID", "0") == "1"   # off by default: on my 5 dosing questions it ranked worse than dense alone (see note below)
K1, B, RRF_K = 1.5, 0.75, 60
W_DENSE, W_BM25 = 1.0, 0.5
_TOK = re.compile(r"[a-z0-9]+|[஀-௿]+")
_STOP = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "are", "what", "how", "my", "do", "does", "i", "me", "it", "with", "at", "by", "should", "can", "when", "which"}

_index: dict = {}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOK.findall((text or "").lower()) if t not in _STOP and len(t) > 1]


def _build(chunks: list[dict]) -> None:
    docs = [_tokens(f"{c.get('crop', '')} {c.get('section', '')} {c.get('text', '')}") for c in chunks]
    df: Counter = Counter()
    for d in docs:
        df.update(set(d))
    n = len(docs)
    _index.update(n=n, docs=[Counter(d) for d in docs], len=np.array([len(d) for d in docs], dtype=np.float32),
                  idf={t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()})
    _index["avg"] = float(_index["len"].mean()) if n else 1.0


def bm25(query: str, chunks: list[dict]) -> np.ndarray:
    if _index.get("n") != len(chunks):
        _build(chunks)
    q = _tokens(query)
    out = np.zeros(len(chunks), dtype=np.float32)
    for i, tf in enumerate(_index["docs"]):
        s = 0.0
        for t in q:
            f = tf.get(t)
            if f:
                s += _index["idf"].get(t, 0.0) * f * (K1 + 1) / (f + K1 * (1 - B + B * _index["len"][i] / _index["avg"]))
        out[i] = s
    return out


def _ranks(scores: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores)
    r = np.empty(len(scores), dtype=np.float32)
    r[order] = np.arange(1, len(scores) + 1)
    return r


def fuse(query: str, chunks: list[dict], dense: np.ndarray) -> np.ndarray:
    """Return one fused score per chunk (higher is better): weighted reciprocal-rank fusion of dense and BM25, then a small rerank that
    favours chunks whose section heading shares words with the question."""
    kw = bm25(query, chunks)
    fused = W_DENSE / (RRF_K + _ranks(dense)) + np.where(kw > 0, W_BM25 / (RRF_K + _ranks(kw)), 0.0)
    q = set(_tokens(query))
    for i in np.argsort(-fused)[:30]:                      # rerank only the leading candidates
        c = chunks[i]
        head = set(_tokens(c.get("section", "")))
        boost = 0.0
        if q & head:
            boost += 0.02 * min(2, len(q & head))
        fused[i] += boost
    return fused


# MEASURED NOTE: on 11 spot-check questions, fusion helped disease and treatment-name questions (sugarcane sett treatment, banana sigatoka) but ranked
# the wrong crop or section first on fertiliser-dose questions (rice urea, cotton nitrogen, maize top dressing). Until a retrieval eval set exists
# to tune the weights, dense search stays the default. Turn on with CROPSY_HYBRID=1 to try it.


# --- named-condition bonus -------------------------------------------------------------------------------------------------------------
# A short question such as "rice blast control" is matched by a variety-note chunk that merely says "susceptible to blast" while the chunk that
# lists the blast sprays ranks sixth. A rare word in the question (blast, sigatoka, shootfly) that a chunk really contains is a strong sign it is the
# right chunk, so such chunks get a small bonus. It only reorders candidates; the cosine score used by the sufficiency test is untouched.
TERM_BONUS = os.getenv("CROPSY_TERMBONUS", "1") == "1"
_RARE_MAX_DF, _PER_TERM, _CAP = 40, 0.03, 0.06
_df_cache: dict = {}
_PHRASES = ("seed rate", "spacing", "sowing time", "seed treatment", "basal", "top dressing")
_PHRASE_BONUS = 0.05


def term_bonus(query: str, chunks: list[dict]) -> np.ndarray:
    out = np.zeros(len(chunks), dtype=np.float32)
    if not TERM_BONUS or not chunks:
        return out
    key = id(chunks)
    if _df_cache.get("key") != key or _df_cache.get("n") != len(chunks):
        docs = [set(_tokens(c.get("text", ""))) for c in chunks]
        df: Counter = Counter()
        for d in docs:
            df.update(d)
        crops = {w for c in chunks for w in _tokens(c.get("crop", ""))}
        _df_cache.update(key=key, n=len(chunks), docs=docs, df=df, crops=crops, texts=[(c.get("text") or "").lower() for c in chunks])
    docs, df, crops = _df_cache["docs"], _df_cache["df"], _df_cache["crops"]
    low = (query or "").lower()
    for ph in _PHRASES:                                                  # "seed rate", "spacing"...: the chunk that has the phrase beats chunks that only talk about the crop
        if ph in low:
            for i, d in enumerate(_df_cache["texts"]):
                if ph in d:
                    out[i] += _PHRASE_BONUS
    terms = [t for t in set(_tokens(query)) if len(t) >= 4 and t not in crops and 0 < df.get(t, 0) <= _RARE_MAX_DF]
    for i, d in enumerate(docs):
        out[i] += min(_CAP, _PER_TERM * sum(1 for t in terms if t in d)) if terms else 0.0
    return out
