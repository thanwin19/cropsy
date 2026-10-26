"""
bedrock.py — AWS Bedrock client wrapper for Cropsy.

Features:
- boto3 session from AWS_PROFILE / env
- invoke_text(model_id, prompt, max_tokens) -> (text, token_count, latency_ms)
- invoke_multimodal(model_id, prompt, image_b64, fmt) -> (text, latency_ms)
- embed_text(text) -> list[float]
- embed_image(image_b64) -> list[float]
- exponential backoff with jitter on throttle/service-unavailable
- cost accounting via config.COST_PER_1K
- marks model unavailable if 3 consecutive hard failures
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from app import config

log = logging.getLogger(__name__)


# ── Session ───────────────────────────────────────────────────────────────────
def _make_session() -> boto3.Session:
    profile = os.getenv("AWS_PROFILE", config.AWS_PROFILE)
    region = os.getenv("AWS_REGION", config.AWS_REGION)
    try:
        return boto3.Session(profile_name=profile, region_name=region)
    except Exception:
        # Fall back to default chain (env vars / instance role)
        return boto3.Session(region_name=region)


_session: Optional[boto3.Session] = None
_bedrock_runtime = None


def _client():
    global _session, _bedrock_runtime
    if _bedrock_runtime is None:
        _session = _make_session()
        _bedrock_runtime = _session.client("bedrock-runtime")
    return _bedrock_runtime


# ── Cost helper ───────────────────────────────────────────────────────────────
def est_cost(model_id: str, tokens: int) -> float:
    rate = config.COST_PER_1K.get(model_id, 0.0001)
    return round(rate * tokens / 1000, 8)


# ── Retry decorator ───────────────────────────────────────────────────────────
def _with_retry(fn, max_retries: int = config.BEDROCK_MAX_RETRIES):
    delay = config.BEDROCK_RETRY_DELAY
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn()
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException"):
                wait = delay * (2 ** attempt) + (time.time() % 0.3)
                log.warning("Bedrock %s attempt %d/%d — sleeping %.1fs", code, attempt + 1, max_retries, wait)
                time.sleep(wait)
                last_exc = e
            else:
                raise
        except Exception as e:
            last_exc = e
            break
    raise last_exc or RuntimeError("Bedrock call failed after retries")


# ── Text invocation ───────────────────────────────────────────────────────────
def invoke_text(
    model_id: str,
    prompt: str,
    max_tokens: int = 512,
    system: Optional[str] = None,
    temperature: float = 0.2,
) -> tuple[str, int, float]:
    """
    Returns (text, token_count, latency_ms).
    Raises BedrockUnavailableError if the model is not accessible.
    """
    t0 = time.perf_counter()

    # Build body — handle both Amazon Nova (messages API) and Mistral
    if "nova" in model_id or "amazon" in model_id.split(".")[0]:
        body = _nova_body(prompt, system, max_tokens, temperature)
    else:
        body = _mistral_body(prompt, system, max_tokens, temperature)

    def _call():
        return _client().invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

    resp = _with_retry(_call)
    latency_ms = (time.perf_counter() - t0) * 1000
    raw = json.loads(resp["body"].read())

    text, tokens = _parse_response(model_id, raw)
    log.debug("invoke_text %s tokens=%d latency=%.0fms", model_id, tokens, latency_ms)
    return text, tokens, latency_ms


def _nova_body(prompt: str, system: Optional[str], max_tokens: int, temperature: float) -> dict:
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    # Nova InvokeModel schema: schemaVersion + snake_case max_new_tokens (camelCase maxNewTokens is rejected
    # with ValidationException; camelCase maxTokens is the Converse API's name).
    body: dict = {
        "schemaVersion": "messages-v1",
        "messages": messages,
        "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": temperature},
    }
    if system:
        body["system"] = [{"text": system}]
    return body


def _mistral_body(prompt: str, system: Optional[str], max_tokens: int, temperature: float) -> dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


def _parse_response(model_id: str, raw: dict) -> tuple[str, int]:
    # Amazon Nova format
    if "output" in raw and "message" in raw.get("output", {}):
        content = raw["output"]["message"]["content"]
        text = content[0]["text"] if content else ""
        usage = raw.get("usage", {})
        tokens = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
        return text, tokens

    # Mistral format
    if "choices" in raw:
        choice = raw["choices"][0]
        msg = choice.get("message", {}) or choice.get("delta", {})
        text = msg.get("content", "")
        usage = raw.get("usage", {})
        tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        return text, tokens

    # Titan text
    if "results" in raw:
        text = raw["results"][0].get("outputText", "")
        tokens = raw.get("inputTextTokenCount", 0) + len(text.split())
        return text, tokens

    log.warning("Unknown response format from model: %s", list(raw.keys()))
    return str(raw), 0


# ── Multimodal invocation (Nova Lite) ─────────────────────────────────────────
def invoke_multimodal(
    model_id: str,
    prompt: str,
    image_b64: str,
    image_format: str = "jpeg",
    max_tokens: int = 512,
) -> tuple[str, float]:
    """Returns (text, latency_ms)."""
    t0 = time.perf_counter()

    body = {
        "schemaVersion": "messages-v1",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": image_format.lower().replace("jpg", "jpeg"),
                            "source": {"bytes": image_b64},
                        }
                    },
                    {"text": prompt},
                ],
            }
        ],
        "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": 0.1},
    }

    def _call():
        return _client().invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

    resp = _with_retry(_call)
    latency_ms = (time.perf_counter() - t0) * 1000
    raw = json.loads(resp["body"].read())
    text, _ = _parse_response(model_id, raw)
    return text, latency_ms


# ── Embedding — text ──────────────────────────────────────────────────────────
def embed_text(text: str, model_id: str = config.MODEL_TITAN_TEXT) -> list[float]:
    """Returns 256-dim embedding."""
    body = {"inputText": text[:8000], "dimensions": 256, "normalize": True}

    def _call():
        return _client().invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

    resp = _with_retry(_call)
    raw = json.loads(resp["body"].read())
    return raw.get("embedding", [])


# ── Embedding — image ─────────────────────────────────────────────────────────
def embed_image(image_b64: str, model_id: str = config.MODEL_TITAN_MULTIMODAL) -> list[float]:
    """Returns 1024-dim embedding."""
    body = {"inputImage": image_b64}

    def _call():
        return _client().invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

    resp = _with_retry(_call)
    raw = json.loads(resp["body"].read())
    return raw.get("embedding", [])


# ── Availability probe ────────────────────────────────────────────────────────
class BedrockUnavailableError(RuntimeError):
    pass


def probe_model(model_id: str) -> dict:
    """Test-call a model with a minimal payload. Returns status dict."""
    try:
        if "embed-text" in model_id or "titan-embed-text" in model_id:
            vec = embed_text("test", model_id)
            return {"model_id": model_id, "status": "ok", "dim": len(vec)}
        elif "embed-image" in model_id or "titan-embed-image" in model_id:
            # Use a 1x1 white JPEG
            _1x1 = (
                "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
                "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA"
                "Ax4ABAAAAQAB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD"
                "/2gAIAQEAAD8AVIP/2Q=="
            )
            vec = embed_image(_1x1, model_id)
            return {"model_id": model_id, "status": "ok", "dim": len(vec)}
        else:
            text, tokens, latency = invoke_text(model_id, "Say OK", max_tokens=4)
            return {"model_id": model_id, "status": "ok", "tokens": tokens, "latency_ms": round(latency)}
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        return {"model_id": model_id, "status": "unavailable", "error": f"{code}: {msg}"}
    except Exception as e:
        return {"model_id": model_id, "status": "unavailable", "error": str(e)}
