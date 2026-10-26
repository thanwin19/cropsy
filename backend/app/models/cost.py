"""
cost.py — Token / cost accounting helpers.
"""
from __future__ import annotations
from app import config


def tokens_to_cost(model_id: str, tokens: int) -> float:
    rate = config.COST_PER_1K.get(model_id, 0.0001)
    return round(rate * tokens / 1000, 8)


def image_embed_cost(model_id: str = config.MODEL_TITAN_MULTIMODAL) -> float:
    """Titan multimodal charges per image, not per token."""
    return config.COST_PER_1K.get(model_id, 0.00006)
