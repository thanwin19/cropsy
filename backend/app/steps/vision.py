"""
vision.py — Step 2: Extract visible symptoms from an attached image.
Model: Nova Lite (multimodal). Only runs when image_bytes is present.
"""
from __future__ import annotations

import logging
import time

from app import config
from app.models import bedrock
from app.schemas import PipelineState, TraceEntry

log = logging.getLogger(__name__)

VISION_PROMPT = """You are an agricultural plant disease diagnostician for Tamil Nadu, India.
Examine this crop photograph and report:
1. Visible symptoms (list, be specific: colour, pattern, location on plant)
2. Most likely diagnosis (disease, pest, nutrient deficiency, or healthy)
3. Confidence: high / medium / low

Respond in JSON only:
{
  "visual_observations": ["<symptom 1>", "<symptom 2>"],
  "possible_symptom": "<brief label>",
  "diagnosis": "<diagnosis or 'healthy'>",
  "confidence": "high|medium|low"
}"""


def run(state: PipelineState) -> PipelineState:
    if not state.image_bytes:
        return state

    from app.steps import caption
    if caption.run(state):          # Caption -> Judge: describe first, name nothing (falls through to the one-shot step if it cannot run)
        return state

    t0 = time.perf_counter()
    step = "vision"
    model_id = config.MODEL_NOVA_LITE

    try:
        import json, re
        text, latency_ms = bedrock.invoke_multimodal(
            model_id,
            VISION_PROMPT,
            state.image_bytes,
            image_format=state.image_format or "jpeg",
            max_tokens=400,
        )

        # Parse JSON
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[^\n]*\n?", "", text).rstrip("`").strip()
        try:
            parsed = json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            parsed = json.loads(m.group()) if m else {}

        state.visual_observations = parsed.get("visual_observations", [])
        state.possible_symptom = parsed.get("possible_symptom")
        state.diagnosis = parsed.get("diagnosis")

        latency_ms = (time.perf_counter() - t0) * 1000
        cost = config.COST_PER_1K.get(model_id, 0.00006)

        state.trace.append(TraceEntry(
            step=step, tool_or_model=model_id,
            why="Extract visible crop symptoms from user photo",
            status="ok", latency_ms=latency_ms, est_cost_usd=cost,
            input_summary=f"image={state.image_name or 'uploaded'} fmt={state.image_format}",
            output_summary=f"symptom={state.possible_symptom} diag={state.diagnosis}",
        ))
        state.total_cost_usd += cost

    except Exception as e:
        log.warning("Vision step failed: %s", e)
        latency_ms = (time.perf_counter() - t0) * 1000
        state.trace.append(TraceEntry(
            step=step, tool_or_model=model_id,
            why="Image analysis", status="error",
            latency_ms=latency_ms, est_cost_usd=0.0,
            input_summary=f"image={state.image_name}",
            output_summary=f"error: {str(e)[:80]}",
        ))

    return state
