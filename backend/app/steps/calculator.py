"""
calculator.py — Deterministic fertilizer calculator (runs after retrieval, only for calculation requests).

TNAU lists several NPK recommendations per crop (by variety duration, season, soil). We never pick one silently:
every alternative found in the retrieved chunks is computed for the parcel area and cited, so the model only has to
present numbers it was given. Products: urea 46% N, DAP 18-46-0, MOP 60% K2O.
"""
from __future__ import annotations

import re
import time

from app.schemas import PipelineState, TraceEntry

_RATIO = re.compile(
    r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*kg\s*"
    r"(?:N\s*:\s*P2O5\s*:\s*K2O|NPK|N,\s*P2O5\s*and\s*K2O)?",
    re.IGNORECASE,
)
_TRIGGER = re.compile(r"\b(calculate|calculation|how much|quantity|total (urea|dap|mop|fertili[sz]er)|kg of (urea|dap|mop))\b", re.I)


def _kg(x: float) -> int:
    return int(round(x))


def compute(area_ha: float, n: float, p: float, k: float) -> dict:
    n_t, p_t, k_t = n * area_ha, p * area_ha, k * area_ha
    dap = p_t / 0.46
    urea = max(n_t - dap * 0.18, 0) / 0.46
    mop = k_t / 0.60
    return {"N_kg": _kg(n_t), "P2O5_kg": _kg(p_t), "K2O_kg": _kg(k_t),
            "urea_kg": _kg(urea), "dap_kg": _kg(dap), "mop_kg": _kg(mop)}


def run(state: PipelineState) -> PipelineState:
    q = f"{state.query} {state.normalized_query or ''}"
    if not (_TRIGGER.search(q) and state.parcel_context and state.parcel_context.get("area_ha")):
        return state
    t0 = time.perf_counter()
    area = float(state.parcel_context["area_ha"])
    options, seen = [], set()
    for c in state.chunks or []:
        for m in _RATIO.finditer(c.get("text") or ""):
            ratio = tuple(float(x) for x in m.groups())
            if ratio in seen or len(options) >= 3:
                continue
            seen.add(ratio)
            options.append({"recommendation": f"{m.group(1)}:{m.group(2)}:{m.group(3)} kg N:P2O5:K2O per ha",
                            "source": f"{c.get('title', 'TNAU')} p.{c.get('page', '?')}",
                            **compute(area, *ratio)})
    state.calc = {"area_ha": area, "options": options,
                  "assumptions": "urea 46% N; DAP 18-46-0 (its N is credited); MOP 60% K2O; whole kg",
                  "note": "TNAU gives different recommendations by variety duration, season and soil; confirm which applies"}
    state.trace.append(TraceEntry(
        step="tools/fertilizer_calculator", tool_or_model="fertilizer_calculator",
        why="Calculation request: compute quantities deterministically instead of letting the LLM do arithmetic",
        status="ok" if options else "skipped", latency_ms=(time.perf_counter() - t0) * 1000, est_cost_usd=0.0,
        input_summary=f"area={area} ha, chunks={len(state.chunks or [])}",
        output_summary=f"{len(options)} recommendation(s) computed" if options else "no NPK recommendation found in evidence"))
    return state


def answer_from_calculator(state: PipelineState) -> tuple[str, list[str]] | None:
    """The fertilizer answer written straight from the calculator's numbers, so the per-hectare recommendation, the parcel area and the parcel totals can never be mixed up
    by the language model. Each option states: the per-hectare recommendation and its page, then what that is for THIS parcel's area, in kg of nutrient and of each product."""
    c = state.calc
    if not (c and c.get("options")):
        return None
    area = float(c.get("area_ha") or 0)
    if not (0 < area < 10000):
        return None
    pid = state.parcel_id or (state.parcel_context or {}).get("parcel_id") or "This parcel"
    crop = ((state.parcel_context or {}).get("crop") or {}).get("name") or "the crop"
    n = len(c["options"])
    head = (f"{pid} ({crop}, {area:g} ha): TNAU gives {n} fertilizer recommendation{'s' if n > 1 else ''} for this crop, worked out below for your {area:g} ha. "
            "Which one applies depends on the variety's duration, the season and the soil, so please check with your KVK before buying.")
    recs = []
    for o in c["options"]:
        recs.append(f"{o['recommendation']} ({o['source']}): for {area:g} ha that is N {o['N_kg']} kg, P2O5 {o['P2O5_kg']} kg, K2O {o['K2O_kg']} kg in total, "
                    f"which is about urea {o['urea_kg']} kg, DAP {o['dap_kg']} kg and MOP {o['mop_kg']} kg for the whole parcel.")
    recs.append(f"How the totals are worked: {c.get('assumptions', '')}. Split the nitrogen and apply it at the stages the TNAU guide lists for your variety.")
    return head, recs
