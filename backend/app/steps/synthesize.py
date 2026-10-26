"""
synthesize.py — Step 6: Generate grounded answer from parcel context + retrieved chunks.
Route-based model selection:
  ROUTINE / ADVISORY (simple)  -> Nova Micro
  COMPLEX / VISUAL             -> Ministral 8B
No dose may be fabricated: every dose must appear verbatim in a cited chunk.
"""
from __future__ import annotations

import json
import os
import logging
import re
import time
from typing import Any

from app import config
from app.models import bedrock
from app.schemas import PipelineState, TraceEntry

log = logging.getLogger(__name__)

SYSTEM = """You are Cropsy, an agricultural assistant for farmers in Tamil Nadu, and a precise advisory AI.
Understand the farmer's question whether it is in Tamil, Tanglish or English. Use the crop, parcel, conversation history, retrieved TNAU knowledge, photo observations, tool outputs and calculator results when they are given.
Answer the farmer's actual question in clear, practical language and explain recommendations in simple steps, the way a good extension officer would speak to a farmer.
If the information is not enough, say plainly what is uncertain and ask one relevant follow-up question (for example the crop stage or what the leaves look like).
If feedback from automatic checks is given, revise the answer to fix those checks, keep everything that was valid and useful, and never replace a useful answer with a bare refusal because one rule failed.
Rules:
1. Answer only from the evidence provided. Do not invent doses, chemicals or quantities.
2. If a dose appears in the evidence, quote it verbatim with its source.
3. If you cannot find evidence for a specific claim, say "Evidence not available in current knowledge base."
4. Mark all dummy/simulated data with "(dummy data)" in parentheses.
4a. When the question is about a parcel, state its crop, growth stage and days after planting exactly as given in PARCEL CONTEXT.
4b. Never state frequencies, intervals or quantities that are not in the evidence (for example "apply weekly").
4c. For a photo, treat VISUAL REFERENCE MATCHES as the main evidence for the condition: name the condition they agree on;
    if they disagree or similarity is low, say the photo is unclear and ask for a closer photo. Do not invent a disease name.
4d. If WEATHER is marked cached, say the forecast is cached fallback data.
4e. If a CALCULATOR RESULT is given, use its numbers exactly as written and do not do any arithmetic yourself.
4f. Start with the answer itself. Name the specific product, quantity or time when the evidence has it; never write a vague line such as "use appropriate fungicides" when the evidence names them. Put the steps in "recommendations", each with its own timing, quantity and basis (per hectare, per cent, per litre) exactly as the evidence gives it.
4g. Keep each figure with the crop, variety, purpose and basis it has in the evidence. Never join figures from different rows or purposes (for example a nursery rate and a field rate). If the evidence does not show which row or purpose a figure belongs to, say that you cannot tell and ask a short question.
4i. When the farmer asks to compare things or asks for the difference between them (diseases, pests, fertilizers, varieties), answer with a short markdown table (| Item | How to tell | What to do |) using ONLY distinctions that are in the evidence; leave out any cell the evidence does not support. Otherwise do not use tables.
4h. Do not add disclaimers, source lines or "confirm with your KVK" sentences to the answer: the app adds one short note.
5. Respond in structured JSON matching this schema exactly:
{
  "answer": "<the direct answer in the first sentence, with the specific figure, product or time from the evidence; then at most 2 short sentences>",
  "recommendations": ["<recommendation 1>", "..."],
  "actions": {
    "immediate": ["<action>"],
    "next_24_hours": ["<action>"],
    "next_3_to_7_days": ["<action>"],
    "watch_for": ["<observation>"]
  },
  "risks": ["<risk 1>"],
  "why_this_matters": [
    {"parcel_fact": "<fact from parcel>", "mechanism": "<agronomic mechanism>", "claim": "<source claim>", "source": "<source doc>"}
  ],
  "limitations": ["<limitation 1>"]
}"""


TAMIL_CROPS = {"rice": "நெல் (rice)", "maize": "மக்காச்சோளம் (maize)", "banana": "வாழை (banana)", "groundnut": "நிலக்கடலை (groundnut)", "sugarcane": "கரும்பு (sugarcane)",
               "chilli": "மிளகாய் (chilli)", "blackgram": "உளுந்து (blackgram)", "cotton": "பருத்தி (cotton)", "coconut": "தென்னை (coconut)", "turmeric": "மஞ்சள் (turmeric)"}
# Standard agricultural terms, written from general knowledge of TNAU's Tamil usage; they have NOT been reviewed by a native speaker or checked against a TNAU Tamil glossary.
TAMIL_GLOSSARY = ("உரம் (fertilizer), நீர்ப்பாசனம் (irrigation), தெளிக்கவும் (spray), பூச்சி (pest), நோய் (disease), இலைப்புள்ளி (leaf spot), தண்டு துளைப்பான் (stem borer), "
                  "காய்த் துளைப்பான் (pod or fruit borer), இலைப்பேன் (thrips), அசுவினி (aphid), வெள்ளை ஈ (whitefly), சிலந்திப்பேன் (mite), துரு நோய் (rust), வாடல் நோய் (wilt), "
                  "விதை நேர்த்தி (seed treatment), களை (weed), அறுவடை (harvest), எக்டருக்கு (per hectare)")


def _build_prompt(state: PipelineState) -> str:
    lines = [f"Query: {state.normalized_query or state.query}"]
    rg = state.region or {}
    where = ", ".join(x for x in (rg.get("district"), rg.get("state"), rg.get("country")) if x) or "not known"
    lines.append(f"FARMER REGION: {where} (from {rg.get('source', 'unknown')}). The evidence below is from TNAU and applies to Tamil Nadu unless a passage says otherwise. If the farmer is elsewhere, or the region is not known and the answer depends on place, say that plainly instead of presenting Tamil Nadu advice as local advice.")
    if re.search(r"[஀-௿]", state.query or ""):             # Tamil script in the question: a Tamil answer. Tanglish (Roman letters) is answered in simple English.
        lines.append("REPLY LANGUAGE: Tamil. Write every text value of your JSON answer in clear, simple Tamil. Keep numbers, units, parcel ids, index names (NDVI, SAVI ...) and chemical or fertilizer names as they are.")
        lines.append("TAMIL WORDS TO USE EXACTLY: " + TAMIL_GLOSSARY + ". The crop in this question is " + (TAMIL_CROPS.get(config.norm_crop(state.crop_hint or ""), "") or "as the question says") + ". Never replace a crop or pest name with a different one.")

    # Parcel context
    if state.parcel_context:
        p = state.parcel_context
        # Exclude village_summary (handled separately)
        crop = (p.get("crop") or {})
        soil = (p.get("soil") or {})
        mgmt = (p.get("management") or {})
        issue = (p.get("observed_issue") or {})
        provenance = (p.get("provenance") or {}).get("note", "")
        is_dummy = p.get("data_source") == "dummy"
        dummy_tag = " (dummy data)" if is_dummy else ""
        lines.append(f"\nPARCEL CONTEXT{dummy_tag}:")
        lines.append(f"  Crop: {crop.get('name')} variety={crop.get('variety')} stage={crop.get('stage')} dap={crop.get('days_after_planting')}")
        lines.append(f"  Soil: {soil.get('texture')} pH={soil.get('ph')}")
        lines.append(f"  Management: irrigation={mgmt.get('irrigation_type')} days_since_irr={mgmt.get('days_since_last_irrigation')} days_since_fert={mgmt.get('days_since_last_fertilizer')}")
        if issue.get("label"):
            lines.append(f"  Observed issue: {issue.get('label')} severity={issue.get('severity')} symptoms={issue.get('symptoms')}")
        if provenance:
            lines.append(f"  Data provenance: {provenance}")

        # Village summary
        vs = p.get("village_summary")
        if vs:
            lines.append(f"\nVILLAGE STATS: crop={vs['crop_filter']} count={vs['count']} total_area={vs['total_area_ha']}ha")

    # Weather
    if state.weather_data:
        fc = state.weather_data.get("forecast", [])[:3]
        if fc:
            lines.append(f"\nWEATHER ({state.weather_source}):")
            for d in fc:
                lines.append(f"  {d.get('date')}: rain={d.get('rain_mm')}mm tmax={d.get('tmax_c')}C")

    if state.satellite:
        s = state.satellite
        pid_sat = state.parcel_id or (state.parcel_context or {}).get("parcel_id")
        spatial = bool(re.search(r"which (area|part|corner|side)|where|part of|corner|zone|low vegetation|inspect|uneven|patch", f"{state.query} {state.normalized_query or ''}", re.I))
        try:
            from app import field_analysis
            lines.append("\n" + field_analysis.evidence_text(pid_sat, with_zones=spatial))
        except Exception:  # noqa: BLE001
            lines.append(f"\nSATELLITE (real Sentinel-2, as of {s.get('as_of')}): latest NDVI {s.get('latest_ndvi')} on {s.get('latest_date')}; baseline {s.get('baseline_ndvi')}; change {s.get('change')}; status={s.get('status')}")
        lines.append("  HOW TO ANSWER A SATELLITE QUESTION (the answer field should be 3 to 5 plain sentences that include the value and its date): (1) say in one simple sentence what the index measures; (2) give the actual value with its date and say whether it is the latest scene or the monthly composite, "
                     "never mixing the two; (3) compare with the baseline only if one is given above; (4) say plainly what the evidence cannot show (it is a vegetation signal, not a diagnosis, and it is parcel-level unless zones are given); "
                     "(5) suggest what to inspect next. Say vegetation is decreasing only if the status above is watch or stress; a change smaller than 0.05 is normal variation, so say there is no meaningful decrease. A latest-scene value and a monthly-composite value are different things: never describe one as the other. Do not declare the field healthy or unhealthy from one number, never name a disease from NDVI, and use only the numbers listed above.")

    if state.calc and state.calc.get("options"):
        lines.append(f"\nCALCULATOR RESULT (deterministic; parcel area {state.calc['area_ha']} ha; {state.calc['assumptions']}):")
        for o in state.calc["options"]:
            lines.append(f"  {o['recommendation']} [{o['source']}] -> N {o['N_kg']} kg, P2O5 {o['P2O5_kg']} kg, K2O {o['K2O_kg']} kg; "
                         f"urea {o['urea_kg']} kg, DAP {o['dap_kg']} kg, MOP {o['mop_kg']} kg")
        lines.append(f"  NOTE: {state.calc['note']}")

    if state.image_consensus:
        lines.append(f"\nVISUAL REFERENCE MATCHES: {state.image_consensus}")

    if state.visual_caption:
        j = state.caption_judge or {}
        lines.append("\nPHOTO DESCRIPTION (appearance only, written without naming any disease; judged "
                     + ("complete" if j.get("passed") else "INCOMPLETE: treat gaps as uncertain") + "):")
        lines += [f"  {x}" for x in (state.visual_observations or [])]
        lines.append("  Rule: name a disease only if the reference-photo matches or the knowledge evidence support it. The description alone is not a diagnosis; "
                     "report the description in plain words and say what you cannot tell from the photo.")
    # Vision
    elif state.visual_observations:
        lines.append(f"\nVISUAL ANALYSIS: observations={state.visual_observations} symptom={state.possible_symptom} diagnosis={state.diagnosis}")

    # Retrieved knowledge
    if state.chunks:
        lines.append("\nKNOWLEDGE EVIDENCE:")
        for i, c in enumerate(state.chunks, 1):
            lines.append(f"  [{i}] Source: {c.get('title','?')} p.{c.get('page','?')} section={c.get('section','?')}")
            lines.append(f"      {(c.get('text') or '')[:1400]}")      # a pest page puts the symptoms first and the management after about 500 characters; 400 hid it from the model
            if c.get("has_dose"):
                lines.append("      [CONTAINS DOSE — QUOTE VERBATIM IF USED]")

    lines.append("\nReturn JSON only. Do not add markdown.")
    return "\n".join(lines)


def _choose_model(state: PipelineState) -> tuple[str, str]:
    """Returns (model_id, tier)."""
    route = state.route or config.ROUTE_ADVISORY
    override = os.getenv("CROPSY_SYNTH_MODEL")            # model bake-off only: tests/model_bakeoff.py sets this
    if override:
        return override, config.TIER_CHEAP_OPEN
    if route in (config.ROUTE_COMPLEX, config.ROUTE_VISUAL):
        return config.MODEL_MINISTRAL_8B, config.TIER_SMART
    if re.search(r"[஀-௿]", state.query or ""):
        return config.MODEL_MINISTRAL_8B, config.TIER_SMART       # measured on 4 Tamil questions: Nova Micro's Tamil was garbled (wrong words, even a wrong plant); Ministral 8B's was readable
    return config.MODEL_NOVA_MICRO, config.TIER_CHEAP_OPEN


def _fix_mojibake(text: str) -> str:
    """Some model replies come back as UTF-8 bytes read as Latin-1 (Tamil turns into 'à®...'). Re-decode them; leave the text alone if it does not round-trip."""
    if "à" not in text and "Ã" not in text:
        return text
    for enc in ("latin-1", "cp1252"):                   # the same bytes can arrive through either Windows or Latin-1 decoding
        try:
            fixed = text.encode(enc).decode("utf-8")
            if re.search(r"[஀-௿]", fixed) or "Ã" in text:
                return fixed
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


def _parse_synthesis(raw: str) -> dict:
    """Parse the model's JSON. Tolerates code fences, raw newlines inside strings and truncated output;
    never lets raw JSON text leak into the farmer-facing answer."""
    raw = _fix_mojibake(raw.strip())
    if raw.startswith("```"):
        raw = re.sub(r"^```[^\n]*\n?", "", raw).rstrip("`").strip()
    candidates = [raw]
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        candidates.append(m.group())
    for cand in candidates:
        try:
            d = json.loads(cand, strict=False)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    # Salvage fields from damaged / truncated JSON
    salv: dict = {"recommendations": [], "actions": {}, "risks": [], "limitations": []}
    am = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)', raw, re.DOTALL)
    if am:
        try:                                                                  # JSON string escapes only: decoding the bytes as "unicode_escape" turned Tamil into mojibake
            salv["answer"] = json.loads('"' + am.group(1) + '"', strict=False).strip()
        except Exception:
            salv["answer"] = am.group(1).replace("\\n", "\n").replace('\\"', '"').strip()
        rm = re.search(r'"recommendations"\s*:\s*\[(.*?)(?:\]|$)', raw, re.DOTALL)
        if rm:
            salv["recommendations"] = [s.strip() for s in re.findall(r'"((?:[^"\\]|\\.)*)"', rm.group(1))][:6]
        return salv
    plain = re.sub(r"[{}\[\]\"]", "", raw)
    return {"answer": plain[:800].strip(), "recommendations": [], "actions": {}, "risks": [],
            "limitations": ["The model reply was not in the expected format."]}


GENERAL_SYSTEM = (
    "You are Cropsy, an agricultural advisor for Tamil Nadu farmers. The verified TNAU knowledge base has NO source for this question, "
    "so you give general good-practice guidance from general agronomy knowledge.\n"
    "Write: first a short description of 1 or 2 sentences, then 4 to 6 bullet lines (each starting with '- '), grouped by what matters "
    "for the question (for example water, soil, planting, pests, harvest).\n"
    "Tanglish words: payir/payirgal = crops in general (NOT a specific crop; do not name a crop the farmer did not name), uram = fertilizer, pooch/poochi = insect pest, noi = disease, thanni = water, veyil = sun/heat, pattu pona = withered or dried up, ilai = leaf.\n"
    "STRICT RULES:\n"
    "- Reply in the language the farmer used (English or Tamil; Tanglish questions are answered in simple English).\n"
    "- Answer the question fully and practically, like a good extension officer. Give typical published figures when they help (watering, spacing, "
    "timing, fertiliser per acre or per plant, spray strength). Use litres, centimetres, kg, g and ml; never gallons or inches. "
    "Write '(approx.)' immediately after every number.\n"
    "- You may name common fertilisers, organic inputs and commonly used crop-protection products for the problem. Say to follow the product label "
    "and to confirm with the local KVK or agriculture officer before spraying. NEVER recommend a chemical that is banned in India "
    "(for example endosulfan, monocrotophos on vegetables, carbofuran granules on food crops, paraquat misuse); prefer cultural, biological and "
    "neem-based options first.\n"
    "- Do not say any of this comes from TNAU. Remind the farmer that soil, season and plant age change the answer and to confirm locally."
)
_FORBIDDEN = re.compile(
    r"\b(kg|kgs|g|gm|gms|gram|grams|mg|ml|ppm|urea|dap|npk|mop|potash|pesticide|insecticide|fungicide|herbicide)\b|%|பூச்சிக்கொல்லி|பூஞ்சைக்கொல்லி|பூஞ்சை\s*கொல்லி|களைக்கொல்லி|யூரியா|டி\.?ஏ\.?பி|பொட்டாஷ்",
    re.I,
)


def _banned(text: str) -> bool:
    """True if the text names a banned chemical: such a line is dropped, whatever the model said."""
    from app import pesticides
    return any(k == 'banned' for _, k, _ in pesticides.mentioned(text))


def _general_guidance(state: PipelineState) -> tuple[str, list[str]]:
    """Description + bullets for a question the knowledge base cannot answer. Lines that mention chemicals, weights or doses are
    dropped, and a line with a number is kept only if the number is marked (approx.). Returns ('', []) if the model is unavailable."""
    lang = "Tamil" if re.search(r"[஀-௿]", state.query or "") else "simple English"   # Tanglish questions get simple English: the model's Tanglish is unreliable
    text = ""
    for model in (config.MODEL_NOVA_LITE, config.MODEL_NOVA_MICRO):      # a second, cheaper model if the first call fails
        try:
            text, _, _ = bedrock.invoke_text(model, f"Reply in: {lang}\nFarmer's question: {state.query}", system=GENERAL_SYSTEM, max_tokens=600)
            break
        except Exception as e:  # noqa: BLE001
            log.warning("general guidance unavailable on %s: %s", model, e)
    if not text:
        return "", []
    desc_parts, bullets = [], []
    for ln in text.splitlines():
        t = ln.strip()
        if not t or t.startswith("#"):                      # blank lines and markdown headings
            continue
        is_bullet = t.startswith(("-", "*", "•"))
        t = re.sub(r"^(?:[-*•]\s*)+", "", t).replace("**", "").strip()
        m = re.match(r"(?i)(short description|description)\s*:\s*(.+)", t)
        if m:                                               # the model labelled its own description line
            desc_parts.append(m.group(2).strip())
            continue
        if not t or t.endswith(":"):                        # a topic label such as "Watering:" on its own line
            continue
        if is_bullet:
            if _banned(t):
                continue
            if re.search(r"\d", t) and not re.search(r"approx", t, re.I):
                continue
            bullets.append(t)
        elif not bullets:
            desc_parts.append(t)
    desc = " ".join(desc_parts)
    q_numbers = set(re.findall(r"\d+(?:\.\d+)?", state.query or ""))
    if _banned(desc) or (re.search(r"\d", desc) and "approx" not in desc.lower() and not set(re.findall(r"\d+(?:\.\d+)?", desc)) <= q_numbers):       # a figure the farmer typed (pH 8.4) may be repeated back
        desc = ""
    return desc[:400], bullets[:6]


def _coverage_note() -> str:
    names = [c.lower() for c in config.CROPS]
    return (f"Cropsy's verified knowledge base covers {len(names)} crops: {', '.join(names[:-1])} and {names[-1]}. "
            "For other crops or trees it can only give general guidance, not verified TNAU figures.")


DOC_SYSTEM = (
    "You are Cropsy, an agricultural assistant for Tamil Nadu farmers. The farmer attached a document. Its text, read automatically (it may contain reading errors), is given below.\n"
    "Explain what the document is and its main points in simple language. Then say what in it matters for farming (crops, land, soil test values, money, dates, deadlines), if anything. "
    "If it is not about farming, say so plainly and still summarise it. If the farmer asked something specific, answer that from the document. "
    "Never write sentences such as 'no specific question was asked'. "
    "Use ONLY what is in the text: do not invent numbers, names or dates; if a part is unclear, say it is unclear. Reply in the language of the farmer's message "
    "(Tamil script means reply in Tamil; otherwise simple English). Keep it under 220 words, with short bullet lines starting with '- '."
)


DOC_CHUNK = 9000
DOC_MAX_CHUNKS = 60


def _condense(text: str) -> str:
    """A long document does not fit one prompt: summarise it piece by piece (Nova Micro, in parallel), then explain the joined summaries.
    A document of up to about 12,000 characters is passed whole."""
    if len(text) <= 12000:
        return text
    from concurrent.futures import ThreadPoolExecutor
    parts = [text[i:i + DOC_CHUNK] for i in range(0, len(text), DOC_CHUNK)][:DOC_MAX_CHUNKS]

    def summ(part: str) -> str:
        for m in (config.MODEL_NOVA_MICRO, config.MODEL_NOVA_LITE):
            try:
                out, _, _ = bedrock.invoke_text(m, "Summarise this part of a document in at most 120 words, keeping every number, name, date and crop exactly as written. Do not add anything.\n\n" + part,
                                                system="You summarise documents faithfully.", max_tokens=300)
                return out.strip()
            except Exception as e:  # noqa: BLE001
                log.warning("document chunk summary failed on %s: %s", m, e)
        return part[:600]

    with ThreadPoolExecutor(max_workers=6) as ex:
        sums = list(ex.map(summ, parts))
    note = "" if len(text) <= DOC_CHUNK * DOC_MAX_CHUNKS else " (only the first part of a very long document was summarised)"
    return f"[This is a condensed version of a long document of {len(text)} characters{note}]" + chr(10) + chr(10).join(f"Part {i + 1}: {t}" for i, t in enumerate(sums))


def _explain_document(state: PipelineState, t0: float) -> PipelineState:
    lang = "Tamil" if re.search(r"[஀-௿]", state.query) else "simple English"
    answer, model = "", config.MODEL_NOVA_LITE
    doc = _condense(state.doc_text or "")
    for model in (config.MODEL_NOVA_LITE, config.MODEL_NOVA_MICRO):
        try:
            answer, _, _ = bedrock.invoke_text(model, f"Reply in: {lang}\nFarmer's message: {state.query}\n\nDOCUMENT TEXT:\n{doc}", system=DOC_SYSTEM, max_tokens=700)
            break
        except Exception as e:  # noqa: BLE001
            log.warning("document explanation failed on %s: %s", model, e)
    if not answer.strip():
        answer = "I could read the document but could not summarise it just now. Please try again in a moment."
    state.raw_answer = answer.strip()
    state.recommendations = []
    state.route = config.ROUTE_ROUTINE
    state.general_mode = True
    state.limitations = (state.limitations or []) + ["Explained from the text read from your document (it may contain reading errors). Check important numbers against the original."]
    state.trace.append(TraceEntry(step="synthesize", tool_or_model=model, why="Attached document explained from its own text", status="ok",
                                  latency_ms=(time.perf_counter() - t0) * 1000, est_cost_usd=0.0, input_summary=state.query[:80], output_summary="document explanation"))
    return state


def run(state: PipelineState, retry: bool = False) -> PipelineState:
    t0 = time.perf_counter()

    # An attached document: explain what it says in the farmer's language, using only its text
    if state.doc_text:
        return _explain_document(state, t0)

    # Factual parcel question: exact values from the record and the layers, no language model
    if state.force_facts:
        from app.steps import facts
        return facts.build(state)

    # How-to-make / how-to-protect question: the fixed guides, no language model
    if state.force_guide:
        from app.steps import guides
        gs = guides.guide_only(state)
        state.raw_answer = guides.guide_text(gs)
        state.recommendations = []
        state.limitations = (state.limitations or []) + ["Fixed, reviewed guidance with sources. Amounts for your crop come from the TNAU-based answer; check local rules and subsidies with your KVK or the Forest Department."]
        state.trace.append(TraceEntry(step="synthesize", tool_or_model="how_to_guide", why="How-to question answered from the reviewed guides",
                                      status="ok", latency_ms=(time.perf_counter() - t0) * 1000, est_cost_usd=0.0, input_summary=state.query[:80], output_summary="guide"))
        return state

    # INSUFFICIENT: the condition is recognised (query text or photo) but the corpus has no verified advice. No LLM call,
    # so no treatment or dose can be invented.
    if state.route == config.ROUTE_INSUFFICIENT:
        what = state.gap_condition or "this condition"
        state.raw_answer = (
            f"The problem looks like {what}, but the current knowledge base has no verified TNAU management advice "
            "for it, so no treatment or dose is suggested here. Please consult your local TNAU KVK or agricultural "
            "extension officer, and share this photo with them."
        )
        state.recommendations = [
            "Consult your local KVK (Krishi Vigyan Kendra) or agricultural officer for a confirmed diagnosis and treatment.",
            "Remove and isolate badly affected leaves where practical, and avoid spraying unverified chemicals.",
        ]
        state.limitations = (state.limitations or []) + [f"Evidence insufficient: no verified advice for {what} in the knowledge base."]
        state.trace.append(TraceEntry(
            step="synthesize", tool_or_model="insufficient_evidence_handler",
            why="Known evidence gap: refuse to generate treatment advice and refer to an expert",
            status="ok", latency_ms=(time.perf_counter() - t0) * 1000, est_cost_usd=0.0,
            input_summary=state.query[:80], output_summary=f"INSUFFICIENT: {what}"))
        return state

    # OUT_OF_SCOPE: no LLM call needed
    if state.route == config.ROUTE_OUT_OF_SCOPE:
        state.raw_answer = (
            "This query falls outside the scope of the Cropsy knowledge base for Then Malai. "
            "Either the crop is not covered, the disease is not in the reference corpus, or the "
            "request involves a topic (livestock, schemes, loans) not handled here. "
            "Please consult your local TNAU KVK or extension officer."
        )
        state.recommendations = [
            "Contact your local KVK (Krishi Vigyan Kendra) for expert advice.",
            "Call the TNAU helpline for crop-specific guidance.",
        ]
        state.limitations = ["Query is outside the Cropsy advisory scope."]
        latency_ms = (time.perf_counter() - t0) * 1000
        state.trace.append(TraceEntry(
            step="synthesize", tool_or_model="out_of_scope_handler",
            why="Route is OUT_OF_SCOPE — no LLM call needed",
            status="ok", latency_ms=latency_ms, est_cost_usd=0.0,
            input_summary=state.query[:80],
            output_summary="OUT_OF_SCOPE response",
        ))
        return state

    model_id, tier = _choose_model(state)
    prompt = _build_prompt(state)
    if retry:
        # One retry on the stronger open-weight model, told exactly which checks failed
        model_id, tier = config.MODEL_MINISTRAL_8B, config.TIER_SMART
        prompt += ("\n\nYOUR PREVIOUS ANSWER FAILED THESE AUTOMATIC CHECKS. Fix only what the checks name, keep every valid and useful part of the answer, and do not replace it with a generic refusal:\n- "
                   + "\n- ".join(state.verification_flags or ["unspecified"]))
    fallback_used = False

    if state.force_general and not retry:
        # the question is about a plant the knowledge base does not cover: no retrieved passage can answer it
        text, tokens, llm_latency, fallback_used = json.dumps({"answer": "Evidence not available in current knowledge base."}), 0, 0.0, False
    else:
        try:
            text, tokens, llm_latency = bedrock.invoke_text(
                model_id, prompt, system=SYSTEM, max_tokens=1500
            )
            state.synthesis_bedrock_invoked = True
        except Exception as e:
            log.warning("Primary synthesis model %s failed: %s — trying Nova Micro", model_id, e)
            fallback_used = True
            model_id = config.MODEL_NOVA_MICRO
            tier = config.TIER_CHEAP_OPEN
            try:
                text, tokens, llm_latency = bedrock.invoke_text(
                    model_id, prompt, system=SYSTEM, max_tokens=1024
                )
                state.synthesis_bedrock_invoked = True
            except Exception as e2:
                log.error("All synthesis models failed: %s", e2)
                text = json.dumps({
                    "answer": "Advisory generation temporarily unavailable. Please try again.",
                    "recommendations": [],
                    "actions": {},
                    "risks": [],
                    "limitations": ["Bedrock models unavailable."],
                })
                tokens = 0
                llm_latency = 0.0

    parsed = _parse_synthesis(text)

    # Test-harness failure injection: corrupt the FIRST calculator answer with a unit slip so the verifier has to catch it
    if state.inject_failure == "unit_error_in_first_answer" and not retry and state.calc and state.calc.get("options"):
        o = state.calc["options"][0]
        wrong = f"{o['N_kg'] * 10} kg"
        txt = parsed.get("answer", "")
        for num in (o["N_kg"], o["urea_kg"], o["dap_kg"], o["mop_kg"]):
            txt = re.sub(rf"\b{num}\b", str(num * 10), txt)
        parsed["answer"] = txt + f" Total nitrogen needed is {wrong}."
        parsed["recommendations"] = []

    # The corpus had nothing on this: say so plainly, then give clearly labelled general guidance and state what is covered.
    if re.search(r"evidence not available", parsed.get("answer", ""), re.I) and not state.image_bytes and not retry:
        if _HIGH_IMPACT.search((state.query or "") + " " + (state.normalized_query or "")) and help_without_evidence(state):
            # a quantity-type question (seed rate, spacing, dose ...): what decides it, safe next steps and one follow-up question, but no estimated figure
            parsed["answer"], parsed["recommendations"] = state.raw_answer, state.recommendations
            parsed["actions"], parsed["risks"], parsed["why_this_matters"] = {}, [], []
            parsed["limitations"] = list(state.limitations or [])
        else:
            desc, general = _general_guidance(state)
            state.general_mode = bool(general)
            if general and not desc:                       # no opening sentence came back: the first point leads, so the answer never opens with only the label
                desc, general = general[0], general[1:]
            parsed["answer"] = ((f"{desc} " if desc else "")
                                + ("General guidance, not from TNAU: numbers marked (approx.) are rough, so confirm with your KVK or agricultural officer." if general else
                                   "I could not find this in the TNAU guides, and the general-guidance service did not respond just now. Please ask again in a moment."))
            parsed["recommendations"] = general
            parsed["actions"] = {}
            parsed["risks"] = []
            parsed["why_this_matters"] = []
            parsed["limitations"] = (parsed.get("limitations") or []) + ["Not in the verified TNAU knowledge base: this is general guidance, not a TNAU recommendation."]

    state.raw_answer = parsed.get("answer", "")
    state.recommendations = parsed.get("recommendations", [])
    state.actions = parsed.get("actions") or {}
    state.risks = parsed.get("risks", [])
    state.why_this_matters = parsed.get("why_this_matters", [])
    state.limitations = (state.limitations or []) + parsed.get("limitations", [])
    state.synthesis_model_id = model_id
    state.synthesis_model_tier = tier

    latency_ms = (time.perf_counter() - t0) * 1000
    cost = bedrock.est_cost(model_id, tokens)
    state.total_cost_usd += cost

    state.trace.append(TraceEntry(
        step="synthesize",
        tool_or_model=model_id + (" [fallback]" if fallback_used else ""),
        why=f"Generate grounded advisory for route={state.route}",
        status="ok", latency_ms=latency_ms, est_cost_usd=cost,
        input_summary=f"chunks={len(state.chunks)} route={state.route}",
        output_summary=f"answer={state.raw_answer[:80]}...",
    ))
    return state


# ── Help when the guides have no answer ──────────────────────────────────────────────────────────────────────────────
# A bare "not available" helps nobody. When the evidence has no figure, the model explains what decides it, gives safe next steps and asks the one question
# that would let Cropsy answer better. It is told to give NO figures, doses or chemicals: a number here would be an AI estimate dressed up as advice.
_HIGH_IMPACT = re.compile(r"seed\s*rate|seed requirement|spacing|\bdose\b|dosage|how much|how many|per (acre|hectare|ha)\b|fertili[sz]er (rate|amount|quantity)|quantity|spray (rate|strength)|vithai\s*alavu|evlo|எவ்வளவு|அளவு", re.IGNORECASE)


HELP_SYSTEM = (
    "You are Cropsy, an agricultural advisor for farmers in Tamil Nadu. The farmer asked a question and the verified TNAU guides Cropsy holds do NOT contain the exact answer.\n"
    "Do not invent it. Write exactly this, in the language the farmer used (Tamil script means Tamil; otherwise simple English):\n"
    "EXPLAIN: 1 or 2 sentences on what decides the answer for this crop (for example variety, season, soil, planting method, area or irrigation system; mention purpose such as grain, fodder or vegetable ONLY for a crop that really has several uses).\n"
    "- 3 or 4 short bullet lines (each starting with '- ') of safe next steps: where to read the exact figure (seed packet or variety label, the nearest KVK, the TNAU Agritech portal), "
    "and practical points that need no number.\n"
    "ASK: one short question that would let you answer better (for example the variety, season, area or, only where it applies, the purpose).\n"
    "STRICT: write NO numbers, quantities, doses, spacings, dates or percentages anywhere, and name NO pesticide or chemical. Do not claim anything comes from TNAU."
)


def help_without_evidence(state: PipelineState, missing: str = "") -> bool:
    """Replace a bare no-answer with labelled general help plus a follow-up question. Returns True if the answer was replaced."""
    lang = "Tamil" if re.search(r"[஀-௿]", state.query or "") else "simple English"
    crop = (state.crop_hint or "").strip()
    note = f"\nThe crop is {crop}." if crop else ""
    text = ""
    for model in (config.MODEL_NOVA_LITE, config.MODEL_NOVA_MICRO):
        try:
            text, _, _ = bedrock.invoke_text(model, f"Reply in: {lang}\nFarmer's question: {state.query}{note}\nMissing from the guides: {missing or 'the exact figure asked for'}", system=HELP_SYSTEM, max_tokens=500)
            break
        except Exception as e:  # noqa: BLE001
            log.warning("help fallback unavailable on %s: %s", model, e)
    if not text:
        return False
    explain, bullets, ask = "", [], ""
    for ln in text.splitlines():
        t = ln.strip().replace("**", "")
        if not t:
            continue
        m = re.match(r"(?i)explain\s*:\s*(.+)", t)
        a = re.match(r"(?i)ask\s*:\s*(.+)", t)
        if m:
            explain = m.group(1).strip()
        elif a:
            ask = a.group(1).strip()
        elif t.startswith(("-", "*", "•")):
            b = re.sub(r"^(?:[-*•]\s*)+", "", t)
            if not re.search(r"\d", b) and not _banned(b):         # no figure may slip in
                bullets.append(b)
    if re.search(r"\d", explain) or _banned(explain):
        explain = ""
    if re.search(r"\d", ask):
        ask = ""
    if not (explain or bullets):
        return False
    name = f" for {crop.lower()}" if crop and not re.search(r"[஀-௿]", state.query or "") else ""
    lead = ("The TNAU guides Cropsy holds do not have this" + name + ". ") if lang != "Tamil" else "Cropsy வைத்திருக்கும் TNAU வழிகாட்டிகளில் இதற்கான சரியான அளவு இல்லை. "
    state.raw_answer = (lead + explain + (" " + ask if ask else "")).strip()
    state.recommendations = bullets[:4]
    state.sanitized_recommendations = list(state.recommendations)
    state.actions, state.risks = {}, []
    state.general_mode = True
    state.limitations = [l for l in (state.limitations or []) if not re.search(r"\d", l) and not l.lower().startswith(("a figure", "insufficient"))] + [
        "Not in the verified TNAU knowledge base: general guidance, not a TNAU recommendation. No figure is given because none is supported by the guides."]
    return True
