"""
understand.py — Step 1: Normalise query, detect language, extract crop/intent/stage.
Model: Nova Micro (fallback: Ministral 3B). Runs on EVERY request.
"""
from __future__ import annotations

import json
import logging
import re
import time

from app import config
from app.models import bedrock
from app.schemas import PipelineState, TraceEntry

log = logging.getLogger(__name__)

SYSTEM = """You are a multilingual agricultural query parser for Tamil Nadu, India.
Extract information from queries written in English, Tamil, or Tanglish (Tamil written in English letters).
Return ONLY a valid JSON object — no markdown, no explanations.
Schema:
{
  "language": "en" | "ta" | "tanglish",
  "normalized_query": "<English translation if not already English, else original>",
  "crop_hint": "<crop name if mentioned, else null>",
  "intent": "growth_stage" | "pest_disease" | "fertilizer" | "irrigation" | "weather" | "village_query" | "general",
  "stage_hint": "<crop stage if mentioned, else null>"
}"""

# Tanglish keyword patterns
_TANGLISH = re.compile(
    r"\b(nalla|epdi|enna|ellam|solla|thambi|akka|inge|ange|padikanum|kelvi|vandha|illai|theriyuma|evlo|eppo|podanum|seiyalam|marundhu|pooch+i|poochi|uram|vithai|aaguthu|irukku|panna)\b",
    re.IGNORECASE,
)
# Topic words in Tanglish / Tamil. The model's English rewrite sometimes turns them into another topic (uram = fertilizer became "water management",
# pooch marundhu = insect medicine became "when does it flower"), so the farmer's own topic word is checked and the rewrite corrected when it lost it.
_TOPIC_WORDS = [
    ("fertilizer", "fertilizer dose and schedule", r"\b(uram|ura\b|urea|dap|potash|nutrient|manure)|உரம", r"fertili[sz]|manure|nutrient|urea|dap|potash|npk"),
    ("pest", "insect pest control", r"\b(pooch\w*|purugu|puzhu|pezhu)\b|பூச்சி|புழு", r"pest|insect|worm|borer|aphid|whitefly|thrips|caterpillar|bug"),
    ("disease", "disease control", r"\b(noi|nooi|karugal)\b|நோய்", r"disease|blight|rot|wilt|rust|blast|virus|fung"),
    ("seed", "seed rate", r"\b(vithai|vidhai|vithaippu)\b|விதை", r"seed"),
    ("spray", "pesticide spray", r"(?!)", r"spray|pesticide|fung|insect|pest|disease|control"),
    ("weed", "weed control", r"\b(kalai|kalai\s*edu)\b|களை", r"weed"),
    ("harvest", "harvest time", r"\b(aruvadai|aruvadi|aruppu)\b|அறுவடை", r"harvest"),
]
_HOWMUCH = re.compile(r"\b(evlo|evalo|evvalavu|evvalo|ethanai|yevlo)\b|எவ்வளவு", re.IGNORECASE)
_WHEN = re.compile(r"\b(eppo|eppodhu|eppadhu|yeppo)\b|எப்போது", re.IGNORECASE)
_MEDICINE = re.compile(r"\b(marundhu|maruthu|marunthu)\b|மருந்து", re.IGNORECASE)


def _topic_from_words(text: str) -> tuple[str, str] | None:
    """(topic key, English phrase) when the farmer's own words name a topic."""
    t = text.lower()
    hits = [(k, ph, ok) for k, ph, rx, ok in _TOPIC_WORDS if re.search(rx, t)]
    if _MEDICINE.search(t) and not any(k in ("pest", "disease") for k, _, _ in hits):
        hits = [h for h in hits if h[0] != "fertilizer"] or hits
    if len(hits) == 1:
        return hits[0][0], hits[0][1]
    if not hits and _MEDICINE.search(t):
        return "spray", "which pesticide spray for pests and diseases"
    return None


_TAMIL_SCRIPT = re.compile(r"[\u0B80-\u0BFF]")


def _detect_language_fast(text: str) -> str:
    if _TAMIL_SCRIPT.search(text):
        return "ta"
    if _TANGLISH.search(text):
        return "tanglish"
    return "en"


def _parse_llm_json(raw: str) -> dict:
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[^\n]*\n?", "", raw).rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try extracting first {...}
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {}


_TAMIL_CROP_STEMS = {"எள்ள": "sesame", "ஆமணக்க": "castor", "சூரியகாந்த": "sunflower", "சோயா": "soybean", "கம்ப": "cumbu", "கேழ்வரக": "ragi", "கோதுமை": "wheat", "துவரை": "redgram", "பச்சைப்பயற": "greengram", "தட்டைப்பயற": "cowpea", "கொள்ளு": "horsegram", "கொண்டைக்கடலை": "bengalgram", "சோளம்": "sorghum", "நெல்": "rice", "அரிசி": "rice", "மக்காச்சோள": "maize", "கரும்ப": "sugarcane", "தென்னை": "coconut", "வாழை": "banana", "கடலை": "groundnut", "பருத்தி": "cotton",
                     "உளுந்த": "blackgram", "மிளகாய்": "chilli", "மஞ்சள்": "turmeric"}


def _crop_from_words(text: str) -> str | None:
    """A crop named in the words themselves (English, Tanglish alias, or a Tamil stem such as உளுந்தில்). One crop only: if two different crops appear, say nothing."""
    low = text.lower()
    found: set[str] = set()
    maize_free = text.replace("மக்காச்சோள", " ")
    for stem, crop in _TAMIL_CROP_STEMS.items():
        if stem in (maize_free if crop == "sorghum" else text):
            found.add(crop)
    for alias, crop in config.CROP_ALIASES.items():
        if alias.isascii() and re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low):
            found.add(crop)
    for c in config.CROPS:
        if re.search(r"(?<![a-z])" + c.lower() + r"(?![a-z])", low):
            found.add(c.lower())
    if not found:                                    # a misspelled crop name: close to one covered crop and to no other
        import difflib
        names = [c.lower() for c in config.CROPS]
        hits = {m for t in re.findall(r"[a-z]{5,}", low) for m in difflib.get_close_matches(t, names, n=1, cutoff=0.8)}
        for pair in zip(re.findall(r"[a-z]{3,}", low), re.findall(r"[a-z]{3,}", low)[1:]):         # two words run apart: 'sugar caan'
            hits |= set(difflib.get_close_matches("".join(pair), names, n=1, cutoff=0.8))
        found |= hits
    if found == {"turmeric"} and re.search(r"yellow|aagu|aaguthu|aaguthe|maaruthu|niram|ஆகு|மாறு", low) and not re.search(r"turmeric|கிழங்கு|kilangu|rhizome|மஞ்சள் பயிர்|manjal payir", low):
        return None                                  # "manjal ilai yellow aaguthu": manjal is the colour here (leaves turning yellow), not the crop
    if len(found) > 1 and "turmeric" in found:       # the Tamil and Tanglish word for turmeric also means 'yellow' ('yellow mosaic', 'yellow leaves'): another crop in the same question wins
        found.discard("turmeric")
    return next(iter(found)).title() if len(found) == 1 else None


# Words that make a short question depend on the previous answer ("and the seed rate?", "what about its spacing", "athu evlo", "appo vithai alavu").
_FOLLOWUP_CUE = re.compile(r"^(and|also|then|what about|how about|why|how much|when|which)\b|\b(it|its|that|this|same|there|athu|adhu|idhu|ithu|appo|appadiyenral)\b|\b(seed rate|spacing|dose|dosage|variety|varieties|season|sowing|harvest|yield|duration)\b|"""+"(அது|இது|அப்போ|அதற்கு|அதன்|இதற்கு|இதன்)", re.IGNORECASE)


def _is_followup(text: str) -> bool:
    """A short question with no crop word of its own (the caller has already checked that no crop was found)."""
    t = (text or "").strip().lower()
    return len(t.split()) <= 7 and _crop_from_words(text) is None and bool(_FOLLOWUP_CUE.search(t))


def run(state: PipelineState) -> PipelineState:
    t0 = time.perf_counter()
    step = "understand"

    # Fast language detection (no LLM cost for simple cases)
    lang_fast = _detect_language_fast(state.query)

    model_id = config.MODEL_NOVA_MICRO
    fallback_used = False
    text = ""
    tokens = 0

    prompt = f"Query: {state.query}\n\nReturn JSON only."
    try:
        text, tokens, _ = bedrock.invoke_text(model_id, prompt, system=SYSTEM, max_tokens=200)
    except Exception as e:
        log.warning("Nova Micro failed in understand step: %s — trying Ministral 3B", e)
        fallback_used = True
        model_id = config.MODEL_MINISTRAL_3B
        try:
            text, tokens, _ = bedrock.invoke_text(model_id, prompt, system=SYSTEM, max_tokens=200)
        except Exception as e2:
            log.error("Both models failed in understand: %s", e2)
            # Graceful degradation — set defaults
            state.language = lang_fast
            state.normalized_query = state.query
            state.intent = "general"
            latency_ms = (time.perf_counter() - t0) * 1000
            state.trace.append(TraceEntry(
                step=step, tool_or_model="fallback_regex", why="Bedrock unavailable",
                status="fallback", latency_ms=latency_ms,
                est_cost_usd=0.0,
                input_summary=state.query[:80],
                output_summary=f"lang={state.language} intent=general",
            ))
            return state

    parsed = _parse_llm_json(text)

    state.language = parsed.get("language") or lang_fast
    state.normalized_query = parsed.get("normalized_query") or state.query
    hint = parsed.get("crop_hint")
    # The LLM sometimes returns a parcel id ("TM-09") or a list as the "crop": keep real crop words only
    if not isinstance(hint, str) or re.match(r"^\s*tm[-\s]?\d+", hint, re.IGNORECASE) or " and " in hint.lower():
        hint = None
    state.crop_hint = hint
    rule_crop = _crop_from_words(state.query)                  # the farmer's own words only: the model's English rewrite is what may be wrong
    if rule_crop and config.norm_crop(hint or "").title() != rule_crop:                       # the words name exactly one crop and the model said something else (or nothing): the words win
        wrong = (hint or "").strip()
        if wrong and state.normalized_query:                                                  # the model's English rewrite carried the wrong crop (e.g. blackgram heard as coconut): fix it too
            state.normalized_query = re.sub(re.escape(wrong), rule_crop.lower(), state.normalized_query, flags=re.IGNORECASE)
        elif state.normalized_query and rule_crop.lower() not in state.normalized_query.lower():
            state.normalized_query = f"{state.normalized_query} ({rule_crop.lower()})"
        state.crop_hint = rule_crop
    if not rule_crop and state.crop_hint and not _TAMIL_SCRIPT.search(state.query):             # the model named a crop that no word of the question resembles ("payir" = crop in general, heard as cowpea): not a crop
        import difflib
        names = {state.crop_hint.lower(), config.norm_crop(state.crop_hint)} | {a for a, c in config.CROP_ALIASES.items() if c == config.norm_crop(state.crop_hint) and a.isascii()}
        toks = re.findall(r"[a-z]{3,}", state.query.lower())
        if not any(difflib.SequenceMatcher(None, t, n).ratio() >= 0.7 or n in state.query.lower() for t in toks for n in names):
            if state.normalized_query:
                state.normalized_query = re.sub(re.escape(state.crop_hint), "crop", state.normalized_query, flags=re.IGNORECASE)
            state.crop_hint = None
    if state.normalized_query:                                                                # Tanglish crop words in the English rewrite (cholam, milagai, kezhvaragu) are replaced by the crop's English name, which the embeddings understand
        for alias, canon in sorted(config.CROP_ALIASES.items(), key=lambda kv: -len(kv[0])):
            if alias.isascii() and len(alias) >= 4 and re.search(r"(?<![A-Za-z])" + re.escape(alias) + r"(?![A-Za-z])", state.normalized_query, re.IGNORECASE):
                state.normalized_query = re.sub(r"(?<![A-Za-z])" + re.escape(alias) + r"(?![A-Za-z])", canon, state.normalized_query, flags=re.IGNORECASE)
    if rule_crop and state.normalized_query and rule_crop.lower() not in state.normalized_query.lower():       # the rewrite lost the crop (kezhvaragu became 'kudzu'): put the farmer's own crop back
        state.normalized_query = f"{state.normalized_query} ({rule_crop.lower()})"
    topic = _topic_from_words(state.query) if state.language != "en" or _TANGLISH.search(state.query) else None
    if topic and state.normalized_query:                                                      # the rewrite lost the farmer's topic word: rebuild it from the words themselves
        ok = next(ok for k, _, _, ok in _TOPIC_WORDS if k == topic[0])
        if not re.search(ok, state.normalized_query, re.IGNORECASE):
            lead = "how much" if _HOWMUCH.search(state.query) else "when to apply" if _WHEN.search(state.query) and topic[0] == "fertilizer" else ""
            crop_txt = f" for {state.crop_hint.lower()}" if state.crop_hint else ""
            state.normalized_query = f"{lead} {topic[1]}{crop_txt}".strip()
    if not state.crop_hint and state.context_crop and not state.parcel_id and _is_followup(state.query):     # "and the seed rate?" after a wheat answer: the previous crop carries over; a question that names a crop never uses it
        cc = config.norm_crop(state.context_crop).title()
        if cc in config.CROPS:
            state.crop_hint = cc
            if state.normalized_query and cc.lower() not in state.normalized_query.lower():
                state.normalized_query = f"{state.normalized_query} ({cc.lower()})"
    state.intent = parsed.get("intent") or "general"
    state.stage_hint = parsed.get("stage_hint")

    latency_ms = (time.perf_counter() - t0) * 1000
    cost = bedrock.est_cost(model_id, tokens)
    state.total_cost_usd += cost

    state.trace.append(TraceEntry(
        step=step,
        tool_or_model=model_id + (" [fallback]" if fallback_used else ""),
        why="Normalise language, extract crop/intent/stage from every request",
        status="ok",
        latency_ms=latency_ms,
        est_cost_usd=cost,
        input_summary=state.query[:100],
        output_summary=f"lang={state.language} intent={state.intent} crop={state.crop_hint}",
    ))
    return state
