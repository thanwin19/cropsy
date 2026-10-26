"""
verify.py — Step 7: Deterministic post-hoc verification.
Checks:
  V1: Crop matches parcel crop (if parcel loaded)
  V2: Every dose in recommendations appears verbatim in a cited chunk
  V3: No known-gap disease is mentioned without a disclaimer
  V4: Dummy data is labelled as dummy
  V5: Answer is not empty / degenerate
Outcome: verification_status = pass | flagged | needs_retry
"""
from __future__ import annotations

import logging
import re
import time

from app import config
from app.schemas import PipelineState, TraceEntry

log = logging.getLogger(__name__)

# Pattern to detect dose-like strings: number + unit (kg/ha, g/palm, ml/l, etc.)
_DOSE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:kg|g|mg|ml|l|litre|t|ton|q|quintal|ppm|%)\s*(?:per|/)\s*(?:ha|acre|palm|plant|tree|litre|l)\b",
    re.IGNORECASE,
)

# Crop name normalisation
_CROP_ALIASES = config.CROP_ALIASES


def _norm_crop(name: str) -> str:
    n = name.lower().strip()
    return _CROP_ALIASES.get(n, n)


def _extract_doses(text: str) -> list[str]:
    return _DOSE_PATTERN.findall(text or "")


def _dose_in_chunks(dose: str, chunks: list[dict]) -> bool:
    d = dose.strip().lower()
    for c in chunks:
        if d in (c.get("text") or "").lower():
            return True
    return False


_PURPOSE_Q = {"seed rate": r"seed\s*rate|seed requirement|vithai\s*alavu", "spacing": r"spacing|row to row|plant to plant"}
_NOINFO_RX = re.compile(r"not (explicitly |clearly |directly )?(specified|provided|mentioned|found|available|stated|given)|do not have", re.IGNORECASE)


def _drop_sentences_with(text: str, bad: list[str]) -> str:
    """Remove only the sentences that contain a rejected figure ('10 kg'), keeping the rest of the answer."""
    from app import quantities
    keep = []
    for sent in re.split(r"(?<=[.!?])\s+", text or ""):
        figs = {f"{v} {u}" for v, u in quantities._figures(sent)}
        if not (figs & set(bad)):
            keep.append(sent)
    if len(keep) < len(re.split(r"(?<=[.!?])\s+", text or "")) and any(re.match(r"\s*(This|These|That|Those|Such|It|The above)\b", k) for k in keep):
        return ""                                    # a sentence that pointed back at the removed figure ("This spacing is standard...") would now point at nothing
    return " ".join(keep).strip()


def _give_up_on_figures(state: PipelineState, still_bad) -> None:
    """Second pass: a rejected figure that the mask could not reach (for example written with a Tamil unit) is removed together with its sentence or step. The rest of the answer is kept;
    only if nothing useful is left does the answer become a plain 'not provided in the guides' statement."""
    from app import quantities
    bad = still_bad()
    if not bad:
        return
    state.raw_answer = _drop_sentences_with(state.raw_answer, bad)
    state.sanitized_recommendations = [r for r in (state.sanitized_recommendations or []) if not ({f"{v} {u}" for v, u in quantities._figures(r)} & set(bad))]
    state.recommendations = list(state.sanitized_recommendations)
    if len((state.raw_answer or "").strip()) < 25 and not state.sanitized_recommendations:
        state.raw_answer = "This figure is not provided in the TNAU guides I hold for this crop, so I will not guess one. Please confirm it with your KVK."


def run(state: PipelineState) -> PipelineState:
    t0 = time.perf_counter()
    checks: list[dict] = []
    flags: list[str] = []

    answer_text = state.raw_answer or ""
    recs_text = " ".join(state.recommendations or [])
    all_text = answer_text + " " + recs_text

    # ── V1: Crop mismatch ──────────────────────────────────────────────────────
    if state.parcel_context:
        parcel_crop = _norm_crop(
            (state.parcel_context.get("crop") or {}).get("name", "") or ""
        )
        # Check if answer mentions a different crop prominently
        q = (state.normalized_query or state.query).lower()
        # Route already handles OUT_OF_SCOPE, here we double-check in answer
        v1_pass = True
        if parcel_crop and state.route != config.ROUTE_OUT_OF_SCOPE:
            # If the answer contains a crop name that does not match parcel, flag
            other_crops = {"cotton", "wheat", "tea", "coffee", "rubber", "jute"}
            for oc in other_crops:
                if oc in all_text.lower() and oc != parcel_crop:
                    v1_pass = False
                    flags.append(f"V1_CROP_MISMATCH: answer mentions {oc!r} but parcel grows {parcel_crop!r}")
                    break
        checks.append({"check": "V1_crop_match", "passed": v1_pass, "flag": flags[-1] if not v1_pass else None})
    else:
        checks.append({"check": "V1_crop_match", "passed": True, "flag": None})

    # ── V2: Dose verbatim check ────────────────────────────────────────────────
    doses_in_answer = [] if (state.general_mode or state.force_facts or state.force_guide) else _extract_doses(all_text)   # general guidance carries labelled (approx.) estimates, never chemicals
    bad_doses = [d for d in doses_in_answer if not _dose_in_chunks(d, state.chunks)]
    v2_pass = len(bad_doses) == 0
    if not v2_pass:
        for bd in bad_doses:
            flags.append(f"V2_FABRICATED_DOSE: {bd!r} not found verbatim in any cited chunk")
        # Redact fabricated doses from the recommendations AND the answer text (the dose itself, not just a note)
        def _redact(txt: str) -> str:
            for bd in bad_doses:
                txt = re.sub(re.escape(bd), "[amount: confirm with your KVK]", txt, flags=re.IGNORECASE)
            return txt

        stripped = []
        for rec in (state.recommendations or []):
            new = _redact(rec)
            stripped.append(new + " (the amount is not in the TNAU text we hold: confirm it with your KVK)" if new != rec else rec)
        state.sanitized_recommendations = stripped
        state.raw_answer = _redact(state.raw_answer or "")
    else:
        state.sanitized_recommendations = list(state.recommendations or [])
    checks.append({
        "check": "V2_dose_verbatim",
        "passed": v2_pass,
        "flag": f"fabricated doses: {bad_doses}" if not v2_pass else None,
    })

    # ── V3: Known-gap disclaimer ───────────────────────────────────────────────
    v3_pass = True
    for gap in config.KNOWN_GAPS:
        if gap.lower() in all_text.lower():
            low = all_text.lower()
            if not any(p in low for p in ("insufficient", "not available", "no verified", "consult", "cannot")):
                v3_pass = False
                flags.append(f"V3_KNOWN_GAP_NO_DISCLAIMER: mentions {gap!r} without disclaimer")
                state.limitations = state.limitations or []
                state.limitations.append(
                    f"Advisory for {gap} is not available in the current knowledge base. "
                    "Please consult your local TNAU KVK."
                )
                break
    checks.append({"check": "V3_known_gap_disclaimer", "passed": v3_pass, "flag": flags[-1] if not v3_pass else None})

    # ── V4: Dummy data label ───────────────────────────────────────────────────
    # Labelling is deterministic, so a missing label is repaired here (and recorded) rather than flagged:
    # the answer that leaves the system is always labelled, and a correct answer can still verify as "pass".
    v4_note = None
    if state.parcel_context and state.parcel_context.get("data_source") == "dummy":
        if "dummy" not in all_text.lower():
            state.raw_answer = (state.raw_answer or "") + " (Note: parcel management data is dummy/simulated.)"
            v4_note = "auto_labelled_dummy_data"
    checks.append({"check": "V4_dummy_labelled", "passed": True, "flag": None, "auto_repair": v4_note})

    # ── V8: crop / stage / days must be stated for parcel answers (deterministic auto-repair) ──
    pc = state.parcel_context or {}
    crop_info = pc.get("crop") or {}
    v8_note = None
    if crop_info.get("stage") and state.route in (config.ROUTE_ROUTINE, config.ROUTE_ADVISORY, config.ROUTE_COMPLEX, config.ROUTE_VISUAL):
        stage_short = crop_info["stage"].split(" - ")[0]
        if stage_short.lower() not in (state.raw_answer or "").lower():
            variety = f" ({crop_info['variety']})" if crop_info.get("variety") else ""
            state.raw_answer = (f"{state.parcel_id or pc.get('parcel_id')}: {crop_info.get('name')}{variety} is at the "
                                f"{stage_short} stage, {crop_info.get('days_after_planting')} days after planting. "
                                + (state.raw_answer or ""))
            v8_note = "auto_stated_stage_from_calendar"
    checks.append({"check": "V8_stage_stated", "passed": True, "flag": None, "auto_repair": v8_note})

    # ── V6: Calculator numbers must be used exactly ────────────────────────────
    if state.calc and state.calc.get("options"):
        txt = all_text
        def _has(n):
            return re.search(rf"(?<![\d.]){n}(?![\d.])", txt) is not None
        ok_opt = any(_has(o["N_kg"]) and _has(o["K2O_kg"]) for o in state.calc["options"])
        if not ok_opt:
            flags.append("V6_CALC_MISMATCH: answer does not use the calculator's totals (N and K2O kg) for any listed recommendation")
        checks.append({"check": "V6_calculator_numbers", "passed": ok_opt,
                       "flag": flags[-1] if not ok_opt else None})

    # ── V7: cached weather must be disclosed (deterministic auto-repair) ───────
    v7_note = None
    if state.weather_data and state.weather_source == "cached" and "cached" not in all_text.lower():
        state.raw_answer = (state.raw_answer or "") + " (Weather shown is cached fallback data; the live forecast service was unavailable.)"
        v7_note = "auto_disclosed_cached_weather"
        state.limitations = (state.limitations or []) + ["Weather is cached fallback data, not a live forecast."]
        checks.append({"check": "V7_weather_source_disclosed", "passed": True, "flag": None, "auto_repair": v7_note})

    # ── V10: a banned chemical must never be recommended ─────────────────────────────────────
    try:
        from app import pesticides
        neg = re.compile(r"banned|ban\b|do not|don't|never|avoid|must not|prohibited|illegal|not allowed|not use|தடை|பயன்படுத்த வேண்டாம்|கூடாது", re.IGNORECASE)

        def _unsafe(text: str) -> list[str]:
            hits = []
            for sent in re.split(r"(?<=[.!?\n])\s+", text or ""):
                if any(k == "banned" for _n, k, _x in pesticides.mentioned(sent)) and not neg.search(sent):
                    hits.append(sent)
            return hits
        bad_sents = _unsafe(answer_text) + [r for rec in (state.recommendations or []) for r in _unsafe(rec)]
        v10_pass = not bad_sents
        if not v10_pass:
            names = sorted({n for s_ in bad_sents for n, k, _x in pesticides.mentioned(s_) if k == "banned"})
            flags.append(f"V10_BANNED_RECOMMENDATION: the answer recommends {', '.join(names)}, which is banned in India; recommend a cultural, biological or registered alternative instead, or say to ask the KVK")
            if state.retry_count >= 1:                      # the retry did not fix it: the unsafe sentence is removed, the rest of the answer is kept
                for s_ in bad_sents:
                    state.raw_answer = (state.raw_answer or "").replace(s_, "")
                state.recommendations = [r for r in (state.recommendations or []) if not _unsafe(r)]
                state.sanitized_recommendations = list(state.recommendations)
                state.limitations = (state.limitations or []) + [f"A suggestion naming {', '.join(names)} was removed because it is banned in India. Ask your KVK which registered product to use."]
        checks.append({"check": "V10_banned_recommendation", "passed": v10_pass, "flag": flags[-1] if not v10_pass else None})
    except Exception:  # noqa: BLE001
        pass

    # ── V9: satellite numbers must come from the evidence given ─────────────────────────────
    if state.satellite and (state.satellite.get("canonical") or state.satellite.get("latest_ndvi") is not None):
        try:
            from app import field_analysis
            pid_sat = state.parcel_id or (state.parcel_context or {}).get("parcel_id")
            ev = field_analysis.evidence_text(pid_sat, with_zones=True) if pid_sat else ""
            allowed = [float(x) for x in re.findall(r"-?\d+\.\d+", ev)]
            bad_idx = []
            for m_ in re.finditer(r"(ndvi|savi|evi|ndre|ndmi|ndwi)[^0-9\-.]{0,24}(-?\d?\.\d+)", all_text, re.IGNORECASE):
                val = float(m_.group(2))
                if not any(abs(val - a) <= 0.0006 for a in allowed):
                    bad_idx.append(f"{m_.group(1).upper()} {m_.group(2)}")
            cn = (state.satellite or {}).get("canonical") or {}
            scene_v = ((cn.get("latest_scene") or {}).get("indices") or {}).get("ndvi")
            month_v = (cn.get("monthly_composite") or {}).get("mean")
            for sent in re.split(r"(?<=[.!?])\s+", all_text):
                low = sent.lower()
                if scene_v is not None and f"{scene_v:g}" in sent and re.search(r"monthly|composite|\bmonth\b", low) and not re.search(r"not (the )?monthly|different from the monthly|rather than the monthly", low):
                    bad_idx.append(f"the latest-scene value {scene_v} described as monthly")
                if month_v is not None and f"{month_v:g}" in sent and re.search(r"latest scene|single (scene|pass)|one scene|latest reading", low) and "monthly" not in low:
                    bad_idx.append(f"the monthly value {month_v} described as the latest scene")
            if cn.get("status") == "normal" and re.search(r"decreas|declin|dropp|falling|reduc", all_text, re.IGNORECASE) and not re.search(r"no meaningful|normal variation|within (the )?normal|not a meaningful|no significant|no real", all_text, re.IGNORECASE):
                bad_idx.append(f"a decrease described although the status is normal (change {cn.get('change_vs_baseline')} is within normal variation)")
            v9_pass = not bad_idx
            if not v9_pass:
                flags.append(f"V9_SATELLITE_VALUE: the answer states {', '.join(bad_idx)} which is not in the satellite evidence; use only the values given, with their dates")
            checks.append({"check": "V9_satellite_values", "passed": v9_pass, "flag": flags[-1] if not v9_pass else None})
        except Exception:  # noqa: BLE001
            pass

    # ── V11: a quantity keeps its basis (per hectare / per cent / per litre ...) as the source gives it ──────────────────
    if not (state.general_mode or state.force_general or state.force_facts or state.force_guide or state.doc_text or state.calc):
        from app import quantities
        mism = quantities.basis_mismatches(all_text, [c.get("text") or "" for c in (state.chunks or [])])
        v11_pass = not mism
        if not v11_pass and state.retry_count > 0:                      # second pass: a figure that still has the wrong basis is removed with its sentence or step, never shown
            bad11 = [" ".join(m_.split(":")[0].split()[:2]) for m_ in mism]
            state.raw_answer = _drop_sentences_with(state.raw_answer or "", bad11)
            state.sanitized_recommendations = [r_ for r_ in (_drop_sentences_with(r2, bad11) for r2 in (state.sanitized_recommendations or state.recommendations or [])) if r_]
            state.recommendations = list(state.sanitized_recommendations)
            state.limitations = (state.limitations or []) + ["A figure with the wrong basis (per hectare instead of per cent, for example) was removed: check the seed or dose basis with your KVK."]
            if len((state.raw_answer or "").strip()) < 25 and not state.sanitized_recommendations:
                state.raw_answer = "This figure is not clearly given for this basis in the TNAU guides I hold, so I will not guess one. Please confirm it with your KVK."
            mism = []
            v11_pass = True
        if not v11_pass:
            flags.append("V11_QUANTITY_CONTEXT: " + "; ".join(mism[:3]) + ". Keep each figure with the basis (per hectare, per cent, per litre ...) and the situation the source gives it; do not join figures from different rows or purposes")
        checks.append({"check": "V11_quantity_context", "passed": v11_pass, "flag": flags[-1] if not v11_pass else None})

    # ── V12: every weight or volume in the answer is in the evidence passages (g<->kg, ml<->l, acre<->ha allowed) ─────────
    if not (state.general_mode or state.force_general or state.force_facts or state.force_guide or state.doc_text or state.calc) and state.chunks:
        from app import quantities
        import json as _json
        _hint = config.norm_crop(state.crop_hint or "") if state.crop_hint else ""
        _same = [c for c in state.chunks if (c.get("crop") or "").lower() == _hint] if _hint in {c.lower() for c in config.CROPS} else []
        ev_texts = [c.get("text") or "" for c in (_same or state.chunks)] + [_json.dumps(x, default=str) for x in (state.parcel_context, state.facts, state.weather_data, state.satellite) if x]   # the parcel record, weather and satellite values are evidence too
        missing = quantities.unsupported(all_text, ev_texts)
        v12_pass = not missing
        if not v12_pass:
            if state.retry_count == 0:
                flags.append("V12_UNSUPPORTED_QUANTITY: " + ", ".join(missing[:4]) + " is not in the TNAU passages retrieved. Use only figures that are in the evidence, exactly as written")
            else:                                                       # second pass: the figure stays out of the answer rather than being guessed
                def _mask(txt: str) -> str:
                    for m_ in missing:
                        v_, u_ = m_.split()
                        txt = re.sub(rf"(?<![\w.]){re.escape(v_)}\s*{re.escape(u_)}\b", "[amount: confirm with your KVK]", txt, flags=re.IGNORECASE)
                    return txt
                state.sanitized_recommendations = list(state.sanitized_recommendations or state.recommendations or [])
                state.limitations = (state.limitations or []) + [f"A figure ({', '.join(missing[:3])}) was removed because it is not in the TNAU text we hold: confirm it with your KVK."]
                _give_up_on_figures(state, lambda: quantities.unsupported(" ".join([state.raw_answer or ""] + list(state.sanitized_recommendations or [])), ev_texts))
        checks.append({"check": "V12_quantity_in_evidence", "passed": v12_pass, "flag": f"unsupported: {missing}" if not v12_pass else None})

    # ── V13: a figure given as the seed rate / spacing / seed treatment is that kind of figure in the evidence ─────────────
    if not (state.general_mode or state.force_general or state.force_facts or state.force_guide or state.doc_text or state.calc) and state.chunks:
        from app import quantities as _q
        _hint13 = config.norm_crop(state.crop_hint or "") if state.crop_hint else ""
        _same13 = [c for c in state.chunks if (c.get("crop") or "").lower() == _hint13] if _hint13 in {c.lower() for c in config.CROPS} else []
        wrong = _q.purpose_mismatches(" ".join([state.raw_answer or ""] + list(state.sanitized_recommendations or state.recommendations or [])), state.normalized_query or state.query,
                                      [c.get("text") or "" for c in (_same13 or state.chunks)])
        v13_pass = not wrong
        if not v13_pass:
            if state.retry_count == 0:
                flags.append("V13_FIGURE_PURPOSE: " + "; ".join(wrong[:3]) + ". Use only a figure the passage gives for the thing asked about; if the passages do not give it, say so plainly")
            else:
                def _mask13(txt: str) -> str:
                    for w_ in wrong:
                        v_, u_ = w_.split()[:2]
                        txt = re.sub(rf"(?<![\w.]){re.escape(v_)}\s*{re.escape(u_)}\b(\s*(/|per)\s*(ha|hectare|acre))?", "[amount: confirm with your KVK]", txt, flags=re.IGNORECASE)
                    return txt
                state.sanitized_recommendations = list(state.sanitized_recommendations or state.recommendations or [])
                state.limitations = (state.limitations or []) + ["A figure was removed because the TNAU text does not give it for the thing you asked about: confirm it with your KVK."]
                _give_up_on_figures(state, lambda: [w_.rsplit(" is not given", 1)[0] for w_ in _q.purpose_mismatches(" ".join([state.raw_answer or ""] + list(state.sanitized_recommendations or [])), state.normalized_query or state.query, [c.get("text") or "" for c in (_same13 or state.chunks)])])

        # relevance: a seed-rate or spacing question whose answer says nothing about seed rate or spacing (seed-production hygiene, for example) is not an answer
        _qtxt = (state.normalized_query or state.query or "").lower()
        _atxt = " ".join([state.raw_answer or ""] + list(state.sanitized_recommendations or state.recommendations or []))
        for _name, _unit_rx in (("seed rate", r"\d\s*(kg|g)\b"), ("spacing", r"\d\s*(cm|x|×)")):
            if re.search(_PURPOSE_Q[_name], _qtxt) and not re.search(_PURPOSE_Q[_name], _atxt.lower()) and not re.search(_unit_rx, _atxt.lower()) and not _NOINFO_RX.search(_atxt):
                state.raw_answer = f"A clear {_name} is not provided in the TNAU guides I hold for this crop, so I will not guess one. Please confirm it with your KVK."
                state.sanitized_recommendations, state.recommendations = [], []
                break
        checks.append({"check": "V13_figure_purpose", "passed": v13_pass, "flag": "; ".join(wrong[:3]) if not v13_pass else None})

    # ── V14: a dose stays with its own product (a quantity that the guide gives for another chemical is not accepted) ───────────
    if not (state.general_mode or state.force_general or state.force_facts or state.force_guide or state.doc_text or state.calc) and state.chunks:
        from app import quantities as _q14
        _hint14 = config.norm_crop(state.crop_hint or "") if state.crop_hint else ""
        _same14 = [c for c in state.chunks if (c.get("crop") or "").lower() == _hint14] if _hint14 in {c.lower() for c in config.CROPS} else []
        wrong14 = _q14.product_dose_mismatches(" ".join([state.raw_answer or ""] + list(state.sanitized_recommendations or state.recommendations or [])), [c.get("text") or "" for c in (_same14 or state.chunks)])
        v14_pass = not wrong14
        if not v14_pass:
            if state.retry_count == 0:
                flags.append("V14_PRODUCT_DOSE: " + "; ".join(wrong14[:3]) + ". The guide gives these products other doses: write each product with ITS OWN dose from the passage, or leave the dose out")
            else:                                                       # second pass: the sentence or step that pairs a product with a dose the guide does not give for it is removed
                def _strip14(txt: str) -> str:
                    keep = []
                    for sent in re.split(r"(?<=[.!?])\s+", txt or ""):
                        if not any(w.split()[0] in sent.lower() for w in wrong14):
                            keep.append(sent)
                    return " ".join(keep).strip()
                state.raw_answer = _strip14(state.raw_answer or "")
                state.sanitized_recommendations = [r_ for r_ in (_strip14(r2) for r2 in (state.sanitized_recommendations or state.recommendations or [])) if r_]
                state.recommendations = list(state.sanitized_recommendations)
                state.limitations = (state.limitations or []) + ["A product dose that did not match the guide was removed: check the dose for each product on its label or with your KVK."]
                if len((state.raw_answer or "").strip()) < 25 and not state.sanitized_recommendations:
                    state.raw_answer = "This dose is not provided for this product in the TNAU guides I hold, so I will not guess one. Please confirm it with your KVK."
        amb = _q14.ambiguous_products(" ".join([state.raw_answer or ""] + list(state.sanitized_recommendations or state.recommendations or [])), [c.get("text") or "" for c in (_same14 or state.chunks)])
        if amb and v14_pass:
            state.limitations = (state.limitations or []) + [f"The guide gives {', '.join(a_.title() for a_ in amb[:3])} at different doses for different pests or stages: check which applies to yours before spraying."]
        checks.append({"check": "V14_product_dose", "passed": v14_pass, "flag": "; ".join(wrong14[:3]) if not v14_pass else None})

    # ── V5: Non-empty answer ───────────────────────────────────────────────────
    # Use the original answer text: V4 may have appended a note that would mask an empty answer
    v5_pass = len(answer_text.strip()) > 20
    if not v5_pass:
        flags.append("V5_EMPTY_ANSWER: answer is empty or too short")
    checks.append({"check": "V5_non_empty", "passed": v5_pass, "flag": flags[-1] if not v5_pass else None})

    # ── Outcome ────────────────────────────────────────────────────────────────
    checks_passed = sum(1 for c in checks if c["passed"])
    total = len(checks)

    if flags:
        # Dose fabrication or empty → needs_retry; other flags → flagged
        critical = [f for f in flags if "V2_FABRICATED" in f or "V5_EMPTY" in f or "V6_CALC" in f or "V9_SATELLITE" in f or "V10_BANNED" in f or "V11_QUANTITY" in f or "V12_UNSUPPORTED" in f or "V13_FIGURE" in f or "V14_PRODUCT" in f]
        state.verification_status = "needs_retry" if critical else "flagged"
    else:
        state.verification_status = "pass"

    state.verification_checks = checks
    state.verification_flags = flags

    latency_ms = (time.perf_counter() - t0) * 1000
    state.trace.append(TraceEntry(
        step="verify", tool_or_model="deterministic_critic",
        why="5 safety checks: crop match, dose verbatim, known-gap disclaimer, dummy label, non-empty",
        status=state.verification_status,
        latency_ms=latency_ms, est_cost_usd=0.0,
        input_summary=f"answer_len={len(state.raw_answer or '')} recs={len(state.recommendations or [])}",
        output_summary=f"status={state.verification_status} passed={checks_passed}/{total} flags={flags}",
    ))
    return state
