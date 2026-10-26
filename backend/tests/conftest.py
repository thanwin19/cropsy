"""
conftest.py — Pytest fixtures for Cropsy backend tests.
Provides mocked Bedrock client so tests run without AWS credentials.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ── Mock Bedrock responses ────────────────────────────────────────────────────
MOCK_UNDERSTAND_RESPONSE = json.dumps({
    "language": "en",
    "normalized_query": "What growth stage is the crop at TM-03?",
    "crop_hint": "Rice",
    "intent": "growth_stage",
    "stage_hint": "Tillering",
})

MOCK_SYNTHESIS_RESPONSE = json.dumps({
    "answer": "The crop at TM-03 is Rice (ADT 45) at Tillering stage, 39 days after planting. (dummy data)",
    "recommendations": ["Monitor for narrow brown leaf spot.", "Maintain field moisture."],
    "actions": {
        "immediate": ["Inspect leaves for brown spots."],
        "next_24_hours": ["Check irrigation schedule."],
        "next_3_to_7_days": ["Apply top-dress nitrogen if leaves are pale."],
        "watch_for": ["Spread of lesions."]
    },
    "risks": ["Narrow brown leaf spot can reduce yield if untreated."],
    "why_this_matters": [],
    "limitations": []
})


def _mock_invoke_model(modelId="", body="", **kwargs):
    """Return a plausible response for any model."""
    body_dict = json.loads(body) if body else {}
    messages = body_dict.get("messages", [])
    prompt_text = ""
    if messages:
        content = messages[-1].get("content", "")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    prompt_text = item["text"]
        elif isinstance(content, str):
            prompt_text = content

    # Decide which response to give
    if "Return JSON only" in prompt_text and "normalized_query" not in prompt_text:
        # understand step
        response_text = MOCK_UNDERSTAND_RESPONSE
    else:
        response_text = MOCK_SYNTHESIS_RESPONSE

    response_body = {
        "output": {
            "message": {
                "content": [{"text": response_text}]
            }
        },
        "usage": {"inputTokens": 100, "outputTokens": 80}
    }

    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps(response_body).encode()

    mock_resp = MagicMock()
    mock_resp.__getitem__ = lambda self, k: mock_body if k == "body" else None
    return mock_resp


def _mock_embed_text(text, **kwargs):
    """Return a deterministic 256-d embedding."""
    np.random.seed(abs(hash(text[:32])) % (2**31))
    vec = np.random.randn(256).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


@pytest.fixture(autouse=True)
def mock_bedrock(monkeypatch):
    """Patch boto3 so no real AWS calls are made."""
    mock_client = MagicMock()
    mock_client.invoke_model.side_effect = _mock_invoke_model

    mock_session = MagicMock()
    mock_session.client.return_value = mock_client

    monkeypatch.setattr("boto3.Session", lambda **kw: mock_session)

    # Also patch embed_text / embed_image directly
    import app.models.bedrock as bm
    monkeypatch.setattr(bm, "embed_text", _mock_embed_text)
    monkeypatch.setattr(bm, "embed_image", lambda b64: [0.1] * 1024)

    # Reset the cached client so the mock takes effect
    monkeypatch.setattr(bm, "_bedrock_runtime", None)
    monkeypatch.setattr(bm, "_session", None)

    yield mock_client
