"""
pipeline.py — Cropsy advisory pipeline.
Chains all steps in order, accumulates trace, returns Phase7AdvisoryResult.

Pipeline:
  query → understand → (vision) → tools → router → retrieve → synthesize → verify → respond
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from app import config
from app.schemas import (
    AdvisoryRequest,
    Phase7Actions,
    Phase7AdvisoryResult,
    Phase7ModelInfo,
    Phase7Observability,
    Phase7Source,
    Phase7Verification,
    Phase7VerificationCheck,
    PipelineState,
    TraceEntry,
    WhyThisMattersItem,
)
from app.steps import understand, vision, router, tools, retrieve, calculator, synthesize, verify
from app.steps import caption as caption_step

log = logging.getLogger(__name__)


def _with_region(state: PipelineState) -> str | None:
    """The answer, plus a note about where it applies when that matters. The note always goes into the limitations. It is also added to the answer text only when the farmer's region is unknown
    and the question depends on place (so the farmer sees it), never for fixed guide cards, parcel facts or document explanations."""
    ans = state.raw_answer
    try:
        from app import region as _region
        reg = state.region or _region.unknown()
        note = _region.note_for(state.query or "", reg)
        if not note or not ans:
            return ans
        state.region_note = note
        if note not in (state.limitations or []):
            state.limitations = (state.limitations or []) + [note]
        # the note stays out of the answer text (the answer starts and ends with the answer); the chat shows it as a short note under the answer
    except Exception:  # noqa: BLE001
        pass
    return ans


_CITE_MARK = re.compile(r"\s*\((?:from |see |per )?(?:evidence|photo matches?|source)s?\s*\[?\d+\]?[^)]*\)|\s*\[\d+\]|\s*\(dummy data replaced[^)]*\)|\s*\(source:?[\s,;]*\)|\s*\((?:evidence|sources?)(?: from)?[\s,;]*(?:and[\s,;]*)*\)", re.IGNORECASE)


def _clean(text: str | None) -> str | None:
    """Remove the model's internal markers ('(from evidence [1])', '[2]') and the verifier's raw placeholder so the farmer reads plain sentences."""
    if not text:
        return text
    t = _CITE_MARK.sub("", text)
    t = t.replace(" (the amount is not in the TNAU text we hold: confirm it with your KVK)", " (confirm the amount with your KVK)").replace("[amount: confirm with your KVK]", "the amount your KVK advises")
    ph = "the amount your KVK advises"
    if t.count(ph) > 1:                                  # said once is enough: "A or B or C, at the amount your KVK advises"
        first = t.index(ph) + len(ph)
        t = t[:first] + t[first:].replace(" at " + ph, "").replace(ph, "(amount: ask your KVK)")
    return re.sub(r"\s{2,}", " ", t).strip()


def _tidy_limitations(state: PipelineState) -> list[str] | None:
    """One short, non-repeating note list: the generic 'insufficient evidence' line is dropped when the answer is well supported, and duplicates are removed."""
    out, seen = [], set()
    high = (_confidence(state) or {}).get("level") == "high"
    for lim in state.limitations or []:
        key = lim.strip().lower()
        if key in seen or not key:
            continue
        if (high or state.general_mode) and key.startswith("insufficient evidence in knowledge base"):
            continue
        seen.add(key)
        out.append(lim)
    return out or None


_NO_ANSWER_RX = re.compile(r"(கிடைக்கவில்லை|குறிப்பிடப்படவில்லை|not\s+(explicitly\s+|clearly\s+|directly\s+)?(specified|mentioned|available|provided|found|stated|given)|evidence not available|cannot give|no verified|not recommended as specific)", re.IGNORECASE)


def _is_no_answer(state: PipelineState) -> bool:
    """The answer is a plain 'the guides do not have it' (short, no steps). A real answer that happens to say 'dose not specified' in passing is not one."""
    ans = state.raw_answer or ""
    return bool(_NO_ANSWER_RX.search(ans)) and len(ans) < 320 and not any(re.search(r"\d", r) for r in (state.sanitized_recommendations or state.recommendations or []))


def _build_sources(state: PipelineState) -> list[Phase7Source]:
    seen = set()
    sources = []
    if _is_no_answer(state):                                         # the answer says the documents do not contain it: a page cited beside that would look like support
        return sources
    if state.general_mode or state.force_general or state.force_guide or state.doc_text or state.safety_card:      # general guidance, fixed guides and document explanations cite no TNAU passage: a wrong-crop citation would mislead
        return sources
    from app import quantities
    claim_text = " ".join([state.raw_answer or ""] + list(state.recommendations or []))
    pool = [c for c in (state.chunks or []) if not (c.get("relevance_score") is not None and c["relevance_score"] < 0.40)]    # a weak match is not a source
    support = {id(c): quantities.support_score(claim_text, c.get("text") or "") for c in pool}
    if any(support.values()):                                              # the answer states figures or dates: cite the passages that contain them, best first
        top = max(support.values())
        pool = sorted([c for c in pool if support[id(c)] >= max(1, top / 2)], key=lambda c: -support[id(c)])[:3]
    else:
        pool = pool[:2]
    seen_pages = set()
    for c in pool:
        doc_id = c.get("document_id") or c.get("source_file") or "unknown"
        key = (doc_id, c.get("page"))
        if key in seen_pages:
            continue
        seen_pages.add(key)
        sources.append(Phase7Source(
            document_id=doc_id,
            title=c.get("title") or "TNAU Agronomic Guide",
            page=str(c.get("page")) if c.get("page") else None,
            domain="agronomy",
            provenance="authoritative",
        ))
    return sources


def _build_verification(state: PipelineState) -> Phase7Verification:
    checks = [
        Phase7VerificationCheck(
            check=c["check"],
            passed=c["passed"],
            flag=c.get("flag"),
        )
        for c in (state.verification_checks or [])
    ]
    total = len(checks)
    passed = sum(1 for c in checks if c.passed)
    return Phase7Verification(
        status=state.verification_status,
        success=state.verification_status == "pass",
        checks_passed=passed,
        total_checks=total,
        checks=checks,
        flags=state.verification_flags or [],
        sanitized_recommendations=state.sanitized_recommendations,
    )


def _build_observability(state: PipelineState, tools_called: list[str]) -> Phase7Observability:
    titan_invoked = any(
        "titan" in (t.tool_or_model or "").lower()
        for t in (state.trace or [])
    )
    return Phase7Observability(
        route=state.route,
        agent_model=state.synthesis_model_id,
        model_selected=state.synthesis_model_id,
        model_id=state.synthesis_model_id,
        reason=f"Route={state.route} confidence={state.route_confidence:.2f}",
        cost_mode="cost_optimised",
        estimated_cost_usd=round(state.total_cost_usd, 6),
        tools_called=tools_called,
        latency_ms=state.total_latency_ms,
        verified=state.verification_status == "pass",
        raw_query=state.query,
        language=state.language,
        structured_query={
            "intent": state.intent,
            "crop_hint": state.crop_hint,
            "stage_hint": state.stage_hint,
            "parcel_id": state.parcel_id,
        },
        bedrock_invoked=state.synthesis_bedrock_invoked,
        fallback_used=False,
        titan_text_v2_invoked=titan_invoked,
        titan_text_chunks_retrieved=len(state.chunks),
        titan_multimodal_invoked=bool(state.image_bytes) and bool(state.image_matches),
        titan_multimodal_matches=len(state.image_matches),
        evidence_local_sufficient=state.evidence_local_sufficient,
        evidence_gap_detected=state.evidence_gap_detected,
        trace=[t.model_dump() for t in (state.trace or [])],
    )


def _confidence(state: PipelineState) -> dict:
    """A plain-language trust label for the farmer, from what the pipeline actually found. It never overrides the verifier."""
    top = max((float(c.get("relevance_score") or 0) for c in (state.chunks or [])), default=0.0)
    n = len(state.chunks or [])
    why: list[str] = []
    if state.doc_text:
        return {"level": "medium", "label": "Read from your document", "why": ["Explained from the text read from your document (it may contain reading errors). Check important numbers against the original."], "top_score": None}
    if state.image_bytes and (state.visual_agreement or {}).get("status") != "agree" and not state.general_mode:
        return {"level": "medium", "label": "Medium confidence: confirm before acting", "why": ["The photo was compared with reference photos and its own description did not settle the cause: a closer photo or a KVK visit will."], "top_score": round(top, 2)}
    if state.safety_card:
        return {"level": "low", "label": "Check with an officer", "why": ["A dose for a banned or restricted chemical is never given."], "top_score": None}
    if state.force_facts:
        return {"level": "high", "label": "High confidence", "why": ["Read straight from your parcel record and the satellite layers; no guessing involved."], "top_score": None}
    if state.force_guide:
        try:
            from app.steps import guides
            kind = (guides.guide_only(state) or [{}])[0].get("kind")
        except Exception:  # noqa: BLE001
            kind = None
        if kind == "clarify":
            return {"level": "low", "label": "I need more detail", "why": ["The question was not clear enough to answer safely."], "top_score": None}
        if kind == "reviewed":
            return {"level": "high", "label": "Officer reviewed", "why": ["An agriculture officer reviewed and wrote this answer."], "top_score": None}
        if kind in ("priority", "weather", "calendar", "planner", "gallery", "spread", "regret"):
            return {"level": "high", "label": "High confidence", "why": ["Worked out by fixed rules from the forecast, satellite, your parcel record and history; the reasons are listed."], "top_score": None}
        return {"level": "high", "label": "High confidence", "why": ["A fixed, reviewed guide with a named source; check the details with your KVK for your own crop."], "top_score": None}
    if state.route in (config.ROUTE_OUT_OF_SCOPE, config.ROUTE_INSUFFICIENT):
        return {"level": "low", "label": "Check with an officer", "why": ["Cropsy has no verified source for this."], "top_score": round(top, 2)}
    try:
        from app import pesticides
        banned = [n for n, k, _ in pesticides.mentioned(" ".join([state.raw_answer or ""] + list(state.recommendations or []))) if k == "banned"]
    except Exception:  # noqa: BLE001
        banned = []
    if banned:
        return {"level": "low", "label": "Check with an officer", "why": [f"The answer names {', '.join(banned)}, which is banned in India."], "top_score": round(top, 2)}
    try:
        restricted = [n for n, k, _ in pesticides.mentioned(" ".join([state.raw_answer or ""] + list(state.recommendations or []))) if k == "restricted"]
    except Exception:  # noqa: BLE001
        restricted = []
    if restricted:                                                # high-risk advice stays unapproved until a qualified person has reviewed it
        return {"level": "low", "label": "Check with an officer", "why": [f"The answer names {', '.join(restricted)}, a restricted pesticide: confirm the label claim and the current rules with your KVK before using it."], "top_score": round(top, 2)}
    if state.general_mode or state.force_general:
        return {"level": "low", "label": "Check with an officer", "why": ["General guidance, not from a TNAU document for this crop."], "top_score": round(top, 2)}
    if state.verification_status != "pass" and any("V10_BANNED" in f or "V9_SATELLITE" in f for f in (state.verification_flags or [])):
        return {"level": "low", "label": "Check with an officer", "why": ["The automatic checks could not fully verify this answer."], "top_score": round(top, 2)}
    if _NO_ANSWER_RX.search(state.raw_answer or ""):
        return {"level": "low", "label": "Check with an officer", "why": ["The TNAU documents Cropsy searched do not contain a direct answer to this."], "top_score": round(top, 2)}
    score = 0
    if top >= 0.50:
        score += 2
        why.append("It matches TNAU guide passages closely.")
    elif top >= 0.42:
        score += 1
        why.append("It matches TNAU guide passages only partly.")
    else:
        why.append("The TNAU passages found are only a loose match.")
    if n >= 2:
        score += 1
        why.append(f"{n} TNAU passages support it.")
    if state.parcel_context:
        score += 1
        why.append("It uses your parcel's crop and stage.")
    if state.image_bytes and state.image_matches:
        why.append("A photo was compared with reference photos: a match is a hint, not a diagnosis.")
    crop = ((state.parcel_context or {}).get("crop") or {}).get("name") or state.crop_hint
    try:
        from app import knowledge_info
        thin = knowledge_info.depth_of(crop) == "thin"
    except Exception:  # noqa: BLE001
        thin = False
    if thin and score >= 3:
        score = 2
        why.append(f"The TNAU 2020 guide has only a short chapter on {crop}, so confirm with an officer.")
    level, label = ("high", "High confidence") if score >= 3 else ("medium", "Medium confidence: confirm before acting") if score == 2 else ("low", "Check with an officer")
    return {"level": level, "label": label, "why": why, "top_score": round(top, 2)}


def _cross_check(state: PipelineState) -> dict | None:
    """Side-by-side: the fertilizer calculator's own totals versus the numbers in the answer (the same test as verifier check V6, shown to the farmer)."""
    if not (state.calc and state.calc.get("options")):
        return None
    text = " ".join([state.raw_answer or ""] + list(state.recommendations or []))
    has = lambda n: re.search(rf"(?<![\d.]){n}(?![\d.])", text) is not None  # noqa: E731
    rows = [{"recommendation": o["recommendation"], "source": o["source"], "N_kg": o["N_kg"], "P2O5_kg": o["P2O5_kg"], "K2O_kg": o["K2O_kg"],
             "urea_kg": o["urea_kg"], "dap_kg": o["dap_kg"], "mop_kg": o["mop_kg"], "used_in_answer": has(o["N_kg"]) and has(o["K2O_kg"])} for o in state.calc["options"]]
    return {"passed": any(r["used_in_answer"] for r in rows), "area_ha": state.calc.get("area_ha"), "options": rows,
            "note": "The calculator works the totals from TNAU's per-hectare recommendation and the parcel area; the answer must use exactly those totals."}


def _guides(state: PipelineState) -> list[dict]:
    try:
        from app.steps import guides
        if state.force_guide:
            return guides.guide_only(state)
        cards = guides.guides_for(state)
        if state.crop_hint and config.norm_crop(state.crop_hint).title() in config.CROPS:       # the answer is already about this crop: a generic Tamil Nadu season card under it only repeats and distracts
            cards = [c for c in cards if c.get("id") != "season"]
        return cards
    except Exception:  # noqa: BLE001
        return []


def _ref_photos(state: PipelineState) -> list[dict]:
    try:
        from app.steps import refphotos
        return refphotos.reference_photos(state)
    except Exception:  # noqa: BLE001
        return []


def run(request: AdvisoryRequest, inject_failure: str | None = None) -> Phase7AdvisoryResult:
    t_pipeline_start = time.perf_counter()

    q_text, doc_text = request.query, None
    if "[Text read from " in q_text:                       # an attached document: keep the farmer's own words for routing, pass the document text separately
        q_text, _, rest = q_text.partition("[Text read from ")
        doc_text = rest.rsplit("]", 1)[0]
        q_text = q_text.strip() or "Explain this document"
    if not request.parcel_id:                              # a parcel named in the words ("TM-05 ...") is used even when the caller did not send parcel_id
        request = request.model_copy(update={"parcel_id": tools.parcel_from_text(q_text)})
    from app import region as _region
    state = PipelineState(
        doc_text=doc_text,
        region=_region.resolve(q_text, request.region, {"id": request.parcel_id} if request.parcel_id else None),
        query=q_text,
        parcel_id=request.parcel_id,
        context_crop=request.context_crop,
        image_bytes=request.image_bytes,
        image_format=request.image_format,
        image_name=request.image_name,
        inject_failure=inject_failure,
    )

    try:
        state = understand.run(state)
        state = vision.run(state)        # no-op if no image
        state = tools.run(state)         # parcel + weather + village
        state = router.run(state)        # classify route
        state = retrieve.run(state)      # chunks + image matches
        state = caption_step.agree(state)  # does the photo description fit the same condition as the nearest reference photos?
        from app import conflicts
        state = conflicts.annotate(state)  # passages that disagree are shown, never silently chosen between
        state = calculator.run(state)    # deterministic numbers for calculation requests
        state = synthesize.run(state)    # LLM answer
        state = verify.run(state)        # deterministic checks
        if state.verification_status == "needs_retry" and state.route not in (
            config.ROUTE_OUT_OF_SCOPE, config.ROUTE_INSUFFICIENT
        ):
            # Fallback path: one retry on the stronger model, told which checks failed
            state.retry_count += 1
            state.trace.append(TraceEntry(
                step="retry", tool_or_model=config.MODEL_MINISTRAL_8B,
                why="Verifier rejected the answer: regenerate once on the stronger open-weight model",
                status="fallback", latency_ms=0.0, est_cost_usd=0.0,
                input_summary="; ".join(state.verification_flags or [])[:160],
                output_summary="retrying synthesis",
            ))
            state = synthesize.run(state, retry=True)
            state = verify.run(state)
            if state.verification_status == "needs_retry":
                # Still failing: do not present it as verified. Hand over to a human expert.
                state.verification_status = "flagged"
                state.limitations = (state.limitations or []) + [
                    "Some details could not be double-checked automatically: confirm them with your KVK."
                ]
        from app import pesticides as _pest
        from app.steps.synthesize import _HIGH_IMPACT
        _risky = [m for m in _pest.mentioned(state.query or "") if m[1] in ("banned", "restricted")]
        if _risky and _HIGH_IMPACT.search(state.query or "") and not state.image_bytes:
            name, kind, note = _risky[0]                  # a dose for a banned or restricted chemical is never given: say why and offer the useful next step
            state.raw_answer = f"I can't give a dose for {name.title()}: it is {kind} in India ({note}). Please ask your KVK or agriculture officer before using it."
            state.recommendations = state.sanitized_recommendations = [
                "Tell me the weed, pest or disease you are dealing with and which crop, and I will give the TNAU-listed options for it.",
                "Read the product label and ask the KVK what is permitted on your crop and at what stage."]
            state.actions, state.risks, state.force_facts, state.safety_card = {}, [], True, True
            state.limitations = [f"{name.title()} is {kind} in India. Check its current status with your KVK before using it."]
        if state.calc and state.calc.get("options") and not state.general_mode:
            from app.steps import calculator as _calc
            written = _calc.answer_from_calculator(state)
            if written:                          # fertilizer totals come from the calculator, never from the model's own arithmetic
                state.raw_answer, state.recommendations = written[0], written[1]
                state.sanitized_recommendations = list(written[1])
                state.actions, state.risks = {}, []
                state.limitations = []                          # the model's own caveats about a text that is no longer shown are dropped
        from app.steps.synthesize import _HIGH_IMPACT as _HI
        _top = max((float(c.get("relevance_score") or 0) for c in (state.chunks or [])), default=0.0)
        if (_is_no_answer(state) and _top >= 0.7 and not _HI.search(state.query or "") and state.retry_count == 0 and not (state.general_mode or state.force_general or state.force_facts or state.force_guide or state.doc_text or state.image_bytes)):
            state.retry_count += 1                       # the passages are strong but the model gave up: one more attempt on the stronger model before falling back to general help
            state.verification_flags = ["The retrieved TNAU passages do answer this question: use them (name the specific measures and products they give) instead of saying the evidence is missing"]
            state = synthesize.run(state, retry=True)
            state = verify.run(state)
        if (_is_no_answer(state) and not (state.general_mode or state.force_general or state.force_facts or state.force_guide or state.doc_text
                                                                   or state.image_bytes or state.calc or state.parcel_context)
                and state.route in (config.ROUTE_ADVISORY, config.ROUTE_COMPLEX, config.ROUTE_ROUTINE)):
            synthesize.help_without_evidence(state)        # the guides have no answer: explain what decides it, give safe steps, ask the one useful question
    except Exception as e:
        log.exception("Pipeline crash: %s", e)
        return Phase7AdvisoryResult(
            query=request.query,
            parcel_id=request.parcel_id,
            answer=f"An internal error occurred: {e}",
            error={"code": "PIPELINE_ERROR", "message": str(e)},
        )

    total_latency_ms = (time.perf_counter() - t_pipeline_start) * 1000
    state.total_latency_ms = total_latency_ms

    # Build tools_called list from trace
    tools_called = [
        t.step for t in state.trace
        if t.step.startswith("tools/") and t.status == "ok"
    ]

    # Build why_this_matters
    why_items = []
    for w in (state.why_this_matters or []):               # the model sometimes leaves a field null: that is filled with an empty string, never a crash
        try:
            if isinstance(w, dict):
                why_items.append(WhyThisMattersItem(**{k: ("" if w.get(k) is None else str(w.get(k))) for k in ("parcel_fact", "mechanism", "claim", "source")}))
            elif isinstance(w, WhyThisMattersItem):
                why_items.append(w)
        except Exception:  # noqa: BLE001
            continue

    # Actions
    actions_raw = state.actions or {}
    actions = Phase7Actions(
        immediate=actions_raw.get("immediate"),
        next_24_hours=actions_raw.get("next_24_hours"),
        next_3_to_7_days=actions_raw.get("next_3_to_7_days"),
        watch_for=actions_raw.get("watch_for"),
    )

    # Model info
    model_info = Phase7ModelInfo(
        model_id=state.synthesis_model_id or config.MODEL_NOVA_MICRO,
        model_name=(state.synthesis_model_id or "").split(".")[-1],
        tier=state.synthesis_model_tier or config.TIER_CHEAP_OPEN,
        bedrock_invoked=state.synthesis_bedrock_invoked,
        estimated_cost_usd=round(state.total_cost_usd, 6),
        reason=f"Route={state.route} threshold={config.CONFIDENCE_THRESHOLD}",
    )

    try:                                                       # guard-rail: a banned or restricted chemical named in the answer is flagged, never silently passed
        from app import pesticides
        for name, kind, note in pesticides.mentioned(" ".join([state.query or "", state.raw_answer or ""] + list(state.recommendations or []))):
            state.limitations = (state.limitations or []) + [f"{name.title()} is {kind} in India ({note}). Check its current status with your KVK before using it."]
    except Exception:  # noqa: BLE001
        pass

    if state.image_bytes and state.parcel_id:
        try:
            from app import photo_findings
            photo_findings.record_from_state(state)
        except Exception:  # noqa: BLE001
            pass

    result = Phase7AdvisoryResult(
        parcel_facts=state.facts,
        reference_photos=_ref_photos(state),
        fertilizer_guides=_guides(state),
        confidence=_confidence(state),
        region=state.region,
        doc_values=(__import__("app.media", fromlist=["x"]).doc_values(state.doc_text) or None) if state.doc_text else None,
        crop=(config.norm_crop(state.crop_hint).title() if state.crop_hint and config.norm_crop(state.crop_hint).title() in config.CROPS and not (state.general_mode or state.force_general) else None),
        visual_report=caption_step.report(state),
        cross_check=_cross_check(state),
        parcel_id=state.parcel_id,
        survey_no=state.parcel_id,
        query=state.query,
        task_type=state.intent,
        answer=_clean(_with_region(state)),
        recommendations=[_clean(r) for r in (state.sanitized_recommendations or state.recommendations or [])] or None,
        risks=state.risks,
        actions=actions,
        why_this_matters=why_items if why_items else None,
        sources=_build_sources(state),
        limitations=_tidy_limitations(state),
        model=model_info,
        verification=_build_verification(state),
        verified=state.verification_status == "pass",
        route=state.route,
        model_selected=state.synthesis_model_id,
        tools_called=tools_called,
        cost_mode="cost_optimised",
        estimated_cost_usd=round(state.total_cost_usd, 6),
        observability=_build_observability(state, tools_called),
        possible_symptom=state.possible_symptom,
        visual_observations=state.visual_observations,
        diagnosis=state.diagnosis,
        parcel_context=state.parcel_context,
        image={
            "image_name": state.image_name,
            "analyzed": bool(state.visual_observations),
            "user_uploaded": True,
        } if state.image_bytes else None,
    )
    return result
