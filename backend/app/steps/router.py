"""
router.py — Step 3: Classify request into route with confidence ≥ 0.85.
Routes: ROUTINE / ADVISORY / VISUAL / COMPLEX / OUT_OF_SCOPE
Rule-based first; LLM confirmation for borderline cases.
"""
from __future__ import annotations

import logging
import re
import time

from app import config
from app.steps import facts, guides
from app.schemas import PipelineState, TraceEntry

log = logging.getLogger(__name__)

# ── Rule-based signals ────────────────────────────────────────────────────────
_ROUTINE_PATTERNS = [
    r"\b(stage|days after planting|growth stage|how many days|when was|area|how many parcels|total area|count)\b",
    r"\b(weather|forecast|rain|temperature|humidity|wind)\b",
    r"\b(village|taluk|district|survey no|patta)\b",
]
_ADVISORY_PATTERNS = [
    r"\b(fertilizer|fertiliser|dose|nutrient|nitrogen|phosphorus|potassium|urea|DAP|MOP)\b",
    r"\b(irrigation|water|schedule|apply|spray|basal|top.?dress)\b",
    r"\b(pest|disease|weed|insect|fungus|blight|rot|spot|wilt|armyworm|bollworm)\b",
    r"\b(recommend|advice|advisory|what should|how to|treatment|control|manage)\b",
]
_OUT_OF_SCOPE_PATTERNS = [
    r"\b(jute|tea|coffee|rubber|tobacco)\b",  # crops not in our KB (wheat moved into it in Batch A)
    r"\b(livestock|cattle|goat|poultry|fish|shrimp)\b",
    r"\b(scheme|subsidy|loan|insurance|PM.?kisan)\b",
]
_VISUAL_PATTERNS = [
    r"\b(photo|image|picture|look|see|colour|color|yellow|brown|spot|lesion)\b",
]
# Multi-factor requests combine weather / timing with a crop problem or an operation -> COMPLEX (Ministral 8B)
_WEATHER_WORDS = r"\b(rain|rainfall|forecast|weather|mazhai|storm|shower|drizzle)\b|மழை"
_ACTION_OR_PROBLEM_WORDS = (
    r"\b(spray\w*|fertili[sz]\w*|apply\w*|irrigat\w*|risk\w*|affect\w*|damag\w*|disease\w*|pest\w*|blast|blight|rot|"
    r"spot\w*|yellow\w*|waterlog\w*|drain\w*|podal\w*|manag\w*|control\w*|treat\w*|what should|what to do|plan)\b"
    r"|உரம்|நோய்|மஞ்சள்"
)
_PLANNING_WORDS = r"\b(next (week|7 days|few days|season)|over the next|this season|compare|comparison|plan the)\b"
_CALC_WORDS = r"\b(calculate|calculation|how much|quantity|total (urea|dap|mop|fertili[sz]er)|kg of (urea|dap|mop))\b"

_CROP_MISMATCH = re.compile(
    r"\b(groundnut|cotton|blackgram|chilli|turmeric|wheat|tea|coffee|jute|rubber|tobacco)\b", re.IGNORECASE
)


def _score(text: str, patterns: list[str]) -> float:
    hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
    return min(hits / max(len(patterns), 1), 1.0)


def _detect_crop_mismatch(state: PipelineState) -> bool:
    """Return True if query mentions a crop that contradicts parcel's crop."""
    if not state.parcel_context and state.parcel_id:
        # Router runs before the parcel_lookup tool, so peek at the parcel directly
        from app.steps import tools as _tools
        _tools._load_parcels()
        state.parcel_context = (
            _tools._PARCEL_BY_ID.get(state.parcel_id)
            or _tools._PARCEL_BY_SURVEY.get(state.parcel_id)
        )
    if not state.parcel_context:
        return False
    parcel_crop = (state.parcel_context.get("crop", {}) or {}).get("name", "").lower()
    if not parcel_crop:
        return False
    # Check query asks about a different crop
    q = f"{state.query} {state.normalized_query or ''}"
    m = _CROP_MISMATCH.search(q)
    if m and m.group().lower() not in parcel_crop:
        return True
    return False



# Plants outside the ten-crop knowledge base (English, Tamil and Tanglish names). A question about one of them gets general
# guidance, not a retrieved passage that merely mentions the word (neem cake in a rice schedule is not advice about neem trees).
_UNCOVERED_PLANTS = re.compile(
    r"\b(neem|margosa|veppam|vembu|mango|teak|thekku|eucalyptus|casuarina|tamarind|guava|jackfruit|pomegranate|papaya|moringa|murungai|"
    r"drumstick|brinjal|onion|potato|tea|coffee|rubber|"
    r"bhendi|okra|cabbage|carrot|beans|lemon|orange|sapota|cashew|arecanut|pepper|cardamom|ginger|jasmine|rose)\b"
    r"|வேம்பு|மாமரம்|கத்திரி|வெண்டை|வெங்காயம்|முட்டைகோஸ்|உருளைக்கிழங்கு|மா\s*மரம்|கொய்யா|பப்பாளி|எலுமிச்சை|மாதுளை|திராட்சை|முந்திரி|பாக்கு|மிளகு|ஏலக்காய்|காபி|தேயிலை|ரப்பர்"
    r"|\b(foxtail\s+millet|little\s+millet|kodo\s+millet|barnyard\s+millet|proso\s+millet|mustard|brinjal|eggplant|cucumber|pumpkin|"
    r"napier|jasmine|rose|vendakkai|kathirikai|vengayam)\b",
    re.IGNORECASE,
)
_NEEM_AS_INPUT = re.compile(r"neem[\s-]*(cake|oil|seed|extract|coated|kernel|spray)|\bnske\b|veppam[\s-]*(punnaku|ennai)", re.IGNORECASE)
_COVERED = re.compile(r"\b(" + "|".join(sorted({c.lower() for c in config.CROPS} | set(config.CROP_ALIASES), key=len, reverse=True)) + r")\b", re.IGNORECASE)
_INPUT_WORDS = {"uram", "fertilizer", "fertiliser", "fertilizers", "manure", "water", "pesticide", "spray", "urea", "dap", "potash", "neer", "thanni"}
_GENERIC_HINTS = {"crop", "crops", "plant", "plants", "tree", "trees", "general", "none", "null", "vegetable", "fruit"}


_OTHER_REGIONS = re.compile(
    r"\b(punjab|haryana|uttar pradesh|bihar|west bengal|odisha|orissa|jharkhand|chhattisgarh|madhya pradesh|rajasthan|gujarat|maharashtra|karnataka|kerala|andhra|telangana|assam|"
    r"himachal|uttarakhand|jammu|kashmir|goa|manipur|meghalaya|tripura|nagaland|mizoram|sikkim|arunachal|delhi|pondicherry|puducherry|bangladesh|sri lanka|nepal|pakistan)\b", re.IGNORECASE)


def _other_region(state: PipelineState, q: str) -> str | None:
    """A state or country other than Tamil Nadu is named: the knowledge base holds Tamil Nadu (TNAU) recommendations only, so an answer for another region must be labelled general guidance."""
    if state.parcel_id or state.image_bytes:
        return None
    from app import region as _region
    r = state.region or {}
    if (r.get("state") and r["state"] not in _region.kb_states()) or (r.get("country") and r["country"] != "India"):
        return r.get("state") or r.get("country")
    return None


def _uncovered_plant(state: PipelineState, q: str) -> str | None:
    """The plant the farmer is asking about, if it is outside the knowledge base and no parcel or photo gives the context."""
    if state.parcel_id or state.image_bytes:
        return None
    if _NEEM_AS_INPUT.search(q):
        return None                                   # neem used as a spray or manure for a covered crop
    own = state.query or ""                           # the farmer's own words come first: the model's English rewrite can swap a Tamil millet for cotton
    if not _COVERED.search(own):
        m_own = _UNCOVERED_PLANTS.search(own)
        if m_own:
            return m_own.group(0)
    if _COVERED.search(q):
        return None                                   # a covered crop is named: normal retrieval
    m = _UNCOVERED_PLANTS.search(q)
    if m:
        return m.group(0)
    hint = config.norm_crop(state.crop_hint) if isinstance(state.crop_hint, str) else ""
    if hint and hint not in {c.lower() for c in config.CROPS} and hint not in _GENERIC_HINTS and hint not in _INPUT_WORDS:
        return hint
    return None


def run(state: PipelineState) -> PipelineState:
    t0 = time.perf_counter()
    step = "router"

    q = f"{state.query} {state.normalized_query or ''}".lower()

    # Crop mismatch → OUT_OF_SCOPE regardless
    if _detect_crop_mismatch(state):
        state.route = config.ROUTE_OUT_OF_SCOPE
        state.route_confidence = 0.97
        _append_trace(state, step, t0, "crop_mismatch_detected")
        return state

    # An emergency (flood, fire, poisoning, wild animals in the field now): the emergency steps come first, whatever else was asked
    if not state.image_bytes and (guides.is_emergency(state) or guides.is_planner(state)) and guides.guide_only(state):
        state.route = config.ROUTE_ROUTINE
        state.force_guide = True
        state.route_confidence = 0.95
        _append_trace(state, step, t0, "emergency_guide")
        return state

    # A wildlife question with no parcel named: general, sourced guidance
    if not (state.parcel_id or state.parcel_context) and not state.image_bytes and "wildlife" in facts.topics_asked(q):
        state.route = config.ROUTE_ROUTINE
        state.force_facts = True
        state.route_confidence = 0.9
        _append_trace(state, step, t0, "wildlife_general")
        return state

    # A factual question about a parcel (owner, area, soil, terrain, the satellite layers, photo): answer from the data
    from app.steps import guides_dynamic as _gdyn
    if (state.parcel_id or state.parcel_context) and not state.image_bytes and state.intent != "village_query" and facts.topics_asked(q) and not (_gdyn.INDEX_RX.search(q) or (_gdyn.SAT_Q.search(q) and _gdyn.INTERPRET_RX.search(q))):   # 'what does NDVI mean' is an explanation, not a data lookup
        state.route = config.ROUTE_ROUTINE
        state.force_facts = True
        state.route_confidence = 0.95
        _append_trace(state, step, t0, "parcel_facts")
        return state

    # A how-to-make (home-made fertilizer) or how-to-protect (fence) question: the fixed, sourced guides answer it completely
    if not state.image_bytes and guides.guide_only(state):
        state.route = config.ROUTE_ROUTINE
        state.force_guide = True
        state.route_confidence = 0.92
        _append_trace(state, step, t0, "how_to_guide")
        return state

    # A plant outside the knowledge base: general guidance (labelled), never a loosely matched passage
    plant = _uncovered_plant(state, q) or _other_region(state, q)
    if plant:
        state.route = config.ROUTE_ADVISORY
        state.force_general = True
        state.route_confidence = 0.9
        _append_trace(state, step, t0, f"uncovered_plant: {plant}")
        return state

    # Known gap diseases → OUT_OF_SCOPE
    for gap in config.KNOWN_GAPS:
        if gap.lower() in q:
            state.route = config.ROUTE_INSUFFICIENT
            state.gap_condition = gap
            state.route_confidence = 0.95
            _append_trace(state, step, t0, f"known_gap: {gap}")
            return state

    # Image attached → at least VISUAL
    has_image = bool(state.image_bytes)

    # Score each route
    routine_s = _score(q, _ROUTINE_PATTERNS)
    advisory_s = _score(q, _ADVISORY_PATTERNS)
    oos_s = _score(q, _OUT_OF_SCOPE_PATTERNS)
    visual_s = _score(q, _VISUAL_PATTERNS) + (0.5 if has_image else 0)

    weather_hit = bool(re.search(_WEATHER_WORDS, q, re.IGNORECASE))
    action_hit = bool(re.search(_ACTION_OR_PROBLEM_WORDS, q, re.IGNORECASE))
    planning_hit = bool(re.search(_PLANNING_WORDS, q, re.IGNORECASE))
    if re.search(r"differen(ce|t from)|compar(e|ison)|\bversus\b|\bvs\b|distinguish|tell apart", q, re.IGNORECASE):
        planning_hit = True                      # a comparison needs the stronger model: it follows the table format and keeps both items apart
    calc_hit = bool(re.search(_CALC_WORDS, q, re.IGNORECASE)) and bool(state.parcel_id)

    # OUT_OF_SCOPE wins if strong signal
    if oos_s > 0.3:
        state.route = config.ROUTE_OUT_OF_SCOPE
        state.route_confidence = min(0.5 + oos_s, 0.98)
    elif calc_hit:
        state.route = config.ROUTE_ROUTINE          # deterministic calculator, no free-form reasoning
        state.route_confidence = 0.93
    elif (weather_hit and action_hit) or planning_hit:
        # weather/timing + a crop problem or operation (or an explicit planning/comparison request)
        state.route = config.ROUTE_COMPLEX
        state.route_confidence = 0.90
    elif advisory_s > 0.25 and visual_s > 0.3 and has_image:
        state.route = config.ROUTE_COMPLEX
        state.route_confidence = 0.88
    elif has_image:
        state.route = config.ROUTE_VISUAL           # a photo is the only thing that makes a request VISUAL
        state.route_confidence = 0.90
    elif advisory_s > 0.2:
        state.route = config.ROUTE_ADVISORY
        state.route_confidence = min(0.70 + advisory_s, 0.95)
    elif routine_s > 0.1:
        state.route = config.ROUTE_ROUTINE
        state.route_confidence = min(0.75 + routine_s, 0.97)
    else:
        # Default: try ADVISORY with lower confidence
        state.route = config.ROUTE_ADVISORY
        state.route_confidence = 0.72

    _append_trace(state, step, t0, f"rule-based route={state.route} conf={state.route_confidence:.2f}")
    return state


def _append_trace(state: PipelineState, step: str, t0: float, reason: str):
    latency_ms = (time.perf_counter() - t0) * 1000
    state.trace.append(TraceEntry(
        step=step, tool_or_model="rule_router",
        why="Classify request into route at confidence threshold 0.85",
        status="ok", latency_ms=latency_ms, est_cost_usd=0.0,
        input_summary=(state.normalized_query or state.query)[:100],
        output_summary=f"route={state.route} conf={state.route_confidence:.2f} reason={reason}",
    ))
