"""
guides_dynamic.py: cards built from the farmer's own situation, with no language model and so no AWS cost:

  * clarify  : the question is vague, nonsense, a greeting or not about farming: ask what is needed instead of answering from a loosely matching passage
  * weather  : the 7-day forecast turned into actions (what to do or not do) for the parcel's crop
  * calendar : the crop's growth-stage timeline from its planting date, with a "ask about this stage" button per stage (the model is only used if tapped)
  * identify : a gallery of the common diseases and pests of a crop with a photo and plain symptoms

Rules of thumb here are stated as such; forecast numbers come from Open-Meteo (or the dummy weather file when offline).
"""
from __future__ import annotations

import csv
import difflib
import json
import re
import time
from datetime import date, datetime, timedelta

import requests

from app import config
from app.schemas import PipelineState

# ── farm vocabulary: if none of it appears, the question is not understood ──────────────────────────────────────────────
_VOCAB = """crop crops plant plants field fields farm farmer farming land soil seed seeds sow sowing planting transplant harvest yield price market sell
rice paddy maize corn sugarcane cane coconut banana groundnut peanut cotton blackgram chilli chili turmeric neem tree trees
fertilizer fertiliser fertilizers urea dap potash manure compost vermicompost panchagavya jeevamrutham nutrient nitrogen phosphorus potassium zinc
water irrigation irrigate irrigated drip rain rainfall weather forecast flood drought wind storm hail cyclone heat temperature humidity
pest pests insect insects worm worms caterpillar aphid borer disease diseases blight rust spot spots leaf leaves wilt wilting rot mildew mosaic virus fungus
yellow yellowing brown dry drying dead dying curl curling weed weeds spray spraying pesticide fungicide insecticide herbicide dose dosage
animal animals boar elephant monkey peacock peafowl deer cattle cow goat buffalo fence fencing wildlife
owner area parcel photo image map satellite ndvi layer layers stage days calendar schedule timeline tonne ton kilo
scheme subsidy insurance loan kisan msp mandi storage store stored
vegetation greenness savi evi ndre ndmi ndwi baseline reading readings index indices healthy health vigour growth decreasing declining falling reading
nel payir arisi vayal thanni neer uram maruthu poochi noi ilai mazhai vilai vilaichal aruvadai nadavu vithai mann pasu aadu yaanai panni kurangu vellam vaadal
manjal milagai thennai vazhai karumbu paruthi ulundhu ulundu kadalai cholam kalai kalaikolli pugai thavaram paritharam
photosynthesis transpiration respiration germination pollination photoperiod chlorophyll nitrogen phosphorus potassium nutrient nutrients ecosystem climate monsoon season seasons agriculture agronomy horticulture organic compost manure mulch mulching irrigation drainage erosion salinity sodic acidic alkaline humus microbes bacteria fungi hybrid variety varieties cultivar tillage ploughing harvesting threshing farming farmer farmers""".split()
_TAMIL_ROOTS = ["கரும்ப", "உளுந்த", "புழு", "ரகம்", "தாக்குதல்", "கட்டுப்படுத்த", "பசுமை", "வயல்", "செயற்கைக்கோள்", "பகுதி", "பயிர்", "நெல்", "உரம்", "தண்ணீர்", "நீர்", "மழை", "நோய்", "பூச்சி", "இலை", "மண்", "விலை", "அறுவடை", "விதை", "வயல்", "நிலம்", "மஞ்சள்",
                "வாழை", "தென்னை", "கரும்பு", "மிளகாய்", "பருத்தி", "கடலை", "உளுந்து", "சோளம்", "யானை", "பன்றி", "குரங்கு", "மாடு", "ஆடு", "வெள்ளம்", "வறட்சி", "மானியம்", "காப்பீடு", "வானிலை"]
_TAMIL = re.compile(r"[஀-௿]")
_PARCEL = re.compile(r"\btm\s?-?\s?\d{1,3}\b|\bsurvey\b|\bparcel\b", re.IGNORECASE)
_GREETING = re.compile(r"^\W*(hi+|hello+|hey+|hai|vanakkam|vanakam|good\s+(morning|afternoon|evening|night)|thanks?( you)?|thank u|nandri|ok(ay)?|bye|test(ing)?)\W*$", re.IGNORECASE)
_VAGUE = re.compile(r"\b(crop|plant|field|farm|paddy|tree)s?\b.{0,25}\b(bad|not good|not ok|not well|poor|sick|dying|problem|wrong|issue|trouble)\b|"
                    r"\b(something|anything)\s+(is\s+)?wrong\b|\b(what\s+to\s+do|what\s+should\s+i\s+do|i\s+have\s+a\s+problem|need\s+advice|please\s+advise|tell\s+me\s+something)\b|சரியில்ல|\b(payir|vayal|chedi|pasumai)\s+(nalla|nalla\s*illa|sari\s*illa|sariya\s*illa)\b|nalla\s+illa", re.IGNORECASE)
_SPECIFIC = re.compile(r"yellow|spot|wilt|rot|pest|worm|insect|leaf|leaves|blight|rust|dry|water|rain|fertili|urea|dap|weed|price|harvest|sow|animal|boar|elephant|monkey|"
                       r"flood|drought|fire|poison|calendar|schedule|photo|disease|nutrient|stage|spray|flower|bloom|fruit|yield|grow|seed|sapling|branch|bark|root|shoot|prun", re.IGNORECASE)


def _tokens(q: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", q.lower())


def _has_farm_words(q: str) -> bool:
    if _PARCEL.search(q) or any(r in q for r in _TAMIL_ROOTS):
        return True
    vocab = set(_VOCAB)
    for t in _tokens(q):
        if t in vocab or difflib.get_close_matches(t, vocab, n=1, cutoff=0.82):      # tolerates typos such as 'fertilzer'
            return True
    return False


def _is_tamil(q: str) -> bool:
    return bool(_TAMIL.search(q)) or bool(re.search(r"\b(enna|eppadi|evlo|vendum|irukku|illai|pannum|podanum|sollunga|ungal|enga|yaanai|vanthuduchu)\b", q.lower()))


def _crop_of(state: PipelineState) -> str | None:
    q = f"{state.query} {state.normalized_query or ''}".lower()
    for alias, crop in config.CROP_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", q):
            return crop.capitalize()
    for c in config.CROPS:
        if re.search(rf"\b{c.lower()}\b", q):
            return c
    p = state.parcel_context or {}
    return ((p.get("crop") or {}).get("name")) or None


# ── clarify ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _asks(crop: str | None, ta: bool) -> list[dict]:
    c = crop or "my crop"
    return [
        {"label": "பூச்சி / நோய்" if ta else "A pest or disease", "query": f"What are the common diseases and pests of {c} and how do I identify them?"},
        {"label": "தண்ணீர் / உரம்" if ta else "Water or fertilizer", "query": f"How much water and fertilizer does {c} need now?"},
        {"label": "காட்டு விலங்குகள்" if ta else "Wild animals", "query": f"Which wild animals will damage {c} and how do I protect it?"},
        {"label": "வானிலை" if ta else "Weather this week", "query": "What should I do about the weather this week?"},
    ]


def _names_something(q: str) -> bool:
    """The question already names a crop or a disease or pest (so it is not vague, even if it starts with 'what to do')."""
    from app.steps import caption
    low = q.lower()
    if any(re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low) for n in caption._leak_terms()):
        return True
    from app.steps import router as _router            # a plant outside the ten covered crops (mango, tomato, neem ...) is still a plant the question names
    return bool(_router._UNCOVERED_PLANTS.search(low))


_AMOUNT = re.compile(r"(what|which)\s+(fertili[sz]er|manure|spray|pesticide)|(fertili[sz]er|manure)\s+(should|to|do)\s+(i|we|use)|evlo|evvalavu|எவ்வளவு|how\s+much|how\s+many|\bdose\b|dosage|quantity|\bkg\b|litres?|அளவு", re.IGNORECASE)
_INPUT = re.compile(r"urea|\bdap\b|potash|\bmop\b|fertili[sz]er|uram|உரம்|manure|water|thanni|தண்ணீர்|spray|pesticide|irrigat|neer\b|neeru", re.IGNORECASE)


_CROP_DEPENDENT = re.compile(r"(seed\s*rate|spacing|which variet|sowing\s*time|when\s+to\s+sow|harvest\s*time|vithai\s*alavu)", re.IGNORECASE)


def _crop_in_query(q: str) -> bool:
    low = q.lower()
    names = {c.lower() for c in config.CROPS} | set(config.CROP_ALIASES) | {"paddy", "corn"}
    return any(re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low) for n in names)


def _needs_crop(state: PipelineState, q: str) -> bool:
    """'How much urea?' with no crop named and no parcel picked: the answer depends on the crop, so ask instead of guessing."""
    has_parcel_crop = bool(((state.parcel_context or {}).get("crop") or {}).get("name"))
    if _CROP_DEPENDENT.search(q) and not _crop_in_query(q) and not has_parcel_crop and not state.image_bytes and not state.crop_hint:
        return True                                   # "what is the seed rate?": the figure is different for every crop, so ask which one
    if not (_AMOUNT.search(q) and not _crop_in_query(q) and not has_parcel_crop and not state.image_bytes):
        return False
    typo = any(difflib.get_close_matches(t, ["fertilizer", "fertiliser", "manure", "pesticide", "potash"], n=1, cutoff=0.8) for t in _tokens(q))
    if not (_INPUT.search(q) or typo):
        return False
    try:                                              # a plant outside the 10 crops (neem...) gets general guidance, not a crop question
        from app.steps import router as _router
        if _router._uncovered_plant(state, q):
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


_NOT_A_CROP = {"null", "none", "general", "crop", "crops", "plant", "plants", "all", "tree", "trees", "vegetable", "fruit", "uram", "fertilizer", "fertiliser", "fertilizers", "manure", "water", "pesticide",
              "spray", "urea", "dap", "potash", "neer", "thanni", "uram"}


def _model_understood(state: PipelineState) -> bool:
    """True if the understand step found a farming intent or a real plant name (not a fertilizer or input word mistaken for a crop)."""
    if state.image_bytes:
        return False
    hint = str(state.crop_hint or "").strip().lower()
    if hint and hint not in _NOT_A_CROP:
        return True
    return (state.intent or "general") not in ("general", "unknown", "other", "", "fertilizer_dose")


def clarify_card(state: PipelineState) -> dict | None:
    q = (state.query or "").strip()
    if not q:
        return None
    ta = _is_tamil(q)
    crop = _crop_of(state)
    custom_asks = None
    p = state.parcel_context or {}
    pid = p.get("parcel_id") or state.parcel_id
    if _GREETING.match(q):
        msg = ("வணக்கம்! பயிர், உரம், நீர், நோய், வானிலை அல்லது காட்டு விலங்குகள் பற்றி கேளுங்கள்." if ta else
               "Hello! Ask me about your crop, fertilizer, water, pests and diseases, weather or wild animals. Pick a parcel on the map for advice on your own field.")
        title = "வணக்கம்" if ta else "Hello"
    elif re.search(r"\bTM[-\s]?0*\d{1,4}\b", q, re.IGNORECASE) and not pid and not __import__("app.steps.tools", fromlist=["x"]).parcel_from_text(q):               # a parcel id that does not exist: say so, never answer for some other field
        msg = ("அந்த பார்சல் எண் தென் மலை மாதிரி கிராமத்தில் இல்லை. TM-01 முதல் TM-120 வரை உள்ள ஒன்றை தேர்ந்தெடுக்கவும்." if ta else
               "I could not find that parcel. The demo village (Then Malai) has parcels TM-01 to TM-120 (dummy data): pick one on the map or type a valid id such as TM-05.")
        title = "பார்சல் கிடைக்கவில்லை" if ta else "Parcel not found"
    elif _VAGUE.search(q) and not _SPECIFIC.search(q) and not _names_something(q) and not _model_understood(state):  # farm words but no detail: "my crop is bad"
        issue = ((p.get("observed_issue") or {}).get("label") or "") if p else ""
        extra = f" The record for {pid} shows: {issue}." if pid and issue and issue.lower() != "healthy crop" else ""
        msg = ("நீங்கள் என்ன பிரச்சனை காண்கிறீர்கள்? கீழே ஒன்றைத் தொடவும் அல்லது இலை நிறம், புள்ளிகள், பூச்சிகள், வாடல் பற்றி எழுதுங்கள்." if ta else
               f"I need a little more detail to help. What do you see: yellow leaves, spots, insects, wilting, or animals?{extra} Tap one below or describe it.")
        title = "மேலும் விவரம் தேவை" if ta else "I need a little more detail"
    elif _needs_crop(state, q):
        msg = ("எந்தப் பயிருக்கு? அளவு பயிரைப் பொறுத்தது. கீழே பயிரைத் தொடவும் அல்லது வரைபடத்தில் ஒரு நிலத்தைத் தேர்ந்தெடுக்கவும்." if ta else
               "Which crop is this for? The amount depends on the crop, so tap one below (or pick a parcel on the map) and I will answer for that crop.")
        title = "எந்தப் பயிர்?" if ta else "Which crop?"
        custom_asks = [{"label": c, "query": f"{q} for {c}"} for c in config.CROPS]
    elif _has_farm_words(q) or _names_something(q):
        return None
    elif _model_understood(state):                             # the language model read it as a farming question (castor, napier grass, ellu ...)
        return None
    else:                                                      # no farm word at all: nonsense, off-topic, unreadable
        msg = ("மன்னிக்கவும், உங்கள் கேள்வி எனக்குப் புரியவில்லை. எந்தப் பயிர், என்ன பிரச்சனை என்று சொல்லுங்கள், அல்லது கீழே ஒன்றைத் தொடவும்." if ta else
               "Sorry, I did not understand that, and I do not want to guess about your crop. I answer farm questions only: tell me the crop and what you see, or tap one below.")
        title = "புரியவில்லை" if ta else "I did not understand"
    return {"id": "clarify", "title": title, "kind": "clarify", "message": msg, "steps": [], "photos": ["k_paddy2"], "notes": [], "warning": None,
            "source": {"title": "Cropsy", "url": "https://agritech.tnau.ac.in/"}, "videos": [], "contacts": [], "extra_sources": [], "asks": custom_asks or _asks(crop, ta), "reason": "greeting" if _GREETING.match(q) else "unclear"}


# ── weather actions ──────────────────────────────────────────────────────────────────────────────────────────────────
_WEATHER_ANY = re.compile(r"weather|rain|forecast|mazhai|வானிலை|மழை|spray|irrigat", re.IGNORECASE)
_WEATHER_EXPLICIT = re.compile(r"(weather|rain|forecast).{0,30}(alert|action|what to do|plan|advice|advis)|weather alert|what (should|can) i do .{0,25}(weather|rain|forecast)|வானிலை.{0,20}(எச்சரிக்கை|என்ன செய்ய)", re.IGNORECASE)
_WEATHER_SHORT = re.compile(r"\b(rain|weather|forecast|mazhai|mazhai varuma)\b|மழை|வானிலை", re.IGNORECASE)
_WEATHER_OTHER = re.compile(r"yellow|spot|pest|disease|fertili|urea|spray|harvest|sow|price|leaf|wilt|rot|dose", re.IGNORECASE)
_PARCEL_CACHE: dict = {}


def _village_centre() -> tuple[float, float]:
    if "c" not in _PARCEL_CACHE:
        try:
            ps = json.loads((config.DATA_DIR / "parcels.json").read_text(encoding="utf-8"))
            ps = ps if isinstance(ps, list) else ps.get("parcels", [])
            lat = sum(p["location"]["lat"] for p in ps) / len(ps)
            lon = sum(p["location"]["lon"] for p in ps) / len(ps)
            _PARCEL_CACHE["c"] = (lat, lon)
        except Exception:  # noqa: BLE001
            _PARCEL_CACHE["c"] = (8.92, 77.33)
    return _PARCEL_CACHE["c"]


def _forecast(lat: float, lon: float, pid: str | None) -> tuple[list[dict], str]:
    key = (round(lat, 2), round(lon, 2))
    hit = _PARCEL_CACHE.get(key)
    if hit and time.time() - hit[0] < 900:
        return hit[1], hit[2]
    try:
        r = requests.get(config.OPEN_METEO_URL, params={"latitude": lat, "longitude": lon, "forecast_days": 7, "timezone": "Asia/Kolkata",
                                                         "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,wind_speed_10m_max", "past_days": 5}, timeout=4)
        r.raise_for_status()
        d = r.json()["daily"]
        rows = [{"date": d["time"][i], "rain": d["precipitation_sum"][i] or 0.0, "tmax": d["temperature_2m_max"][i], "wind": (d.get("wind_speed_10m_max") or [None] * 7)[i]}
                for i in range(len(d["time"]))]
        _PARCEL_CACHE[key] = (time.time(), rows, "live forecast (Open-Meteo)")
        return rows, "live forecast (Open-Meteo)"
    except Exception:  # noqa: BLE001
        pass
    rows = []
    try:
        today = str(date.today())
        with open(config.WEATHER_FILE, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["parcel_id"] == (pid or "TM-01") and r["date"] >= today:
                    rows.append({"date": r["date"], "rain": float(r["rain_mm"] or 0), "tmax": float(r["tmax_c"] or 0), "wind": float(r.get("wind_kmh") or 0)})
    except Exception:  # noqa: BLE001
        pass
    return rows[:7], "dummy weather file (live forecast not reachable)"


def _day(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%a %d %b")
    except Exception:  # noqa: BLE001
        return s


def _past_note(past: list[dict]) -> list[str]:
    if not past:
        return []
    days = ", ".join(f"{_day(r['date'])} {r['rain']:.0f} mm" for r in past)
    return [f"Rain received in the last {len(past)} days: {sum(r['rain'] for r in past):.0f} mm ({days}). This is the weather model's analysis of what fell, not a rain gauge."]


def weather_card(state: PipelineState) -> dict | None:
    p = state.parcel_context or {}
    loc = p.get("location") or {}
    lat, lon = (loc.get("lat"), loc.get("lon")) if loc.get("lat") is not None else _village_centre()
    rows_all, src = _forecast(lat, lon, p.get("parcel_id") or state.parcel_id)
    today = str(date.today())
    past = [r for r in rows_all if r["date"] < today]
    rows = [r for r in rows_all if r["date"] >= today][:7]
    if not rows:
        return None
    crop = ((p.get("crop") or {}).get("name") or "").lower()
    acts: list[str] = []
    photos: list[str] = []
    heavy = [r for r in rows if r["rain"] >= 25]
    wet = [r for r in rows if 10 <= r["rain"] < 25]
    hot = [r for r in rows if (r["tmax"] or 0) >= 38]
    windy = [r for r in rows if (r["wind"] or 0) >= 30]
    dry_run = 0
    for r in rows:
        dry_run = dry_run + 1 if r["rain"] < 2 else 0
        if dry_run >= 5:
            break
    if heavy:
        d = ", ".join(_day(r["date"]) for r in heavy[:3])
        acts.append(f"Heavy rain expected ({d}, {max(r['rain'] for r in heavy):.0f} mm or more in a day): open drains and bund cuts beforehand, harvest anything that is ready, and do not spray or put on fertilizer before it.")
        if crop in ("rice",):
            acts.append("Rice: check bunds so water does not breach them, and let excess water out once the rain passes.")
        if crop in ("maize", "banana", "turmeric", "groundnut", "chilli", "cotton", "blackgram"):
            acts.append(f"{crop.capitalize()} does not tolerate standing water: clear drainage first.")
        photos.append("em_flood")
    if wet:
        photos.append("w_rain")
        acts.append("Moderate rain on " + ", ".join(_day(r["date"]) for r in wet[:3]) + ": postpone spraying and fertilizer top-dressing to a dry day; rain washes them off or away.")
    if windy:
        acts.append("Strong wind on " + ", ".join(_day(r["date"]) for r in windy[:3]) + ": do not spray (it drifts), and tie or prop up banana and tall crops" + (" now." if crop == "banana" else "."))
        photos.append("em_storm")
    if hot:
        acts.append("Very hot days (" + ", ".join(_day(r["date"]) for r in hot[:3]) + f", up to {max(r['tmax'] for r in hot):.0f} C): irrigate early morning or evening, mulch the soil, and avoid spraying in the heat of the day.")
        photos.append("em_drought")
    if dry_run >= 5 and not heavy and not wet:
        acts.append("Little or no rain for several days: check soil moisture and plan irrigation; mulch to hold moisture.")
        photos.append("em_drought")
    if not acts:
        photos.append("k_paddy2")
        acts.append("No heavy rain, strong wind or extreme heat in the next 7 days: a good window for routine field work, and for spraying or fertilizer if the crop needs it (calm, cool hours, dry leaves).")
    lines = [f"{_day(r['date'])}: rain {r['rain']:.0f} mm, max {r['tmax']:.0f} C" + (f", wind {r['wind']:.0f} km/h" if r.get("wind") is not None else "") for r in rows]
    return {"id": "weather", "title": "This week's weather and what to do" + (f" ({p.get('parcel_id')}, {crop})" if crop else ""), "kind": "weather",
            "steps": acts, "notes": _past_note(past) + ["Forecast source: " + src + "."], "forecast": [{"day": _day(r["date"]), "rain": round(r["rain"]), "tmax": round(r["tmax"] or 0), "wind": round(r["wind"]) if r.get("wind") is not None else None} for r in rows], "warning": None, "photos": list(dict.fromkeys(photos))[:2], "videos": [], "contacts": [],
            "source": {"title": "Open-Meteo forecast; thresholds are rules of thumb from extension practice", "url": "https://open-meteo.com/"}, "extra_sources": [], "asks": []}


# ── crop calendar ────────────────────────────────────────────────────────────────────────────────────────────────────
_CAL = re.compile(r"calendar|timeline|crop\s+plan|task\s+list|week\s+by\s+week|what\s+to\s+do\s+(this|next)\s+(week|month|stage)|stage[\s-]?wise\s+(plan|calendar|schedule)|cropping\s+plan", re.IGNORECASE)


def calendar_card(state: PipelineState) -> dict | None:
    crop = _crop_of(state)
    if not crop:
        return None
    stages = json.loads((config.DATA_DIR / "crop_stages.json").read_text(encoding="utf-8")).get(crop)
    if not stages:
        return None
    p = state.parcel_context or {}
    c = p.get("crop") or {}
    dap = c.get("days_after_planting") if c.get("name") == crop else None
    plant = (date.today() - timedelta(days=int(dap))) if dap is not None else None
    lines, asks, cur_i = [], [], None
    for i, s in enumerate(stages):
        if dap is not None and s["from_day"] <= dap <= s["to_day"]:
            cur_i = i
    for i, s in enumerate(stages):
        when = ""
        if plant:
            a, b = plant + timedelta(days=s["from_day"]), plant + timedelta(days=s["to_day"])
            when = f" ({a.strftime('%d %b')} to {b.strftime('%d %b')})"
        mark = "  <- you are here" if i == cur_i else ""
        lines.append(f"{s['stage']}: day {s['from_day']} to {s['to_day']}{when}{mark}")
        if cur_i is not None and cur_i <= i <= cur_i + 2:
            asks.append({"label": f"What to do in {s['stage']}", "query": f"What should I do in the {s['stage']} stage of {crop}: water, fertilizer and pests?"})
    if cur_i is None:
        asks = [{"label": f"What to do in {stages[0]['stage']}", "query": f"What should I do in the {stages[0]['stage']} stage of {crop}?"}]
    title = f"{crop} growth-stage calendar" + (f" for {p.get('parcel_id')}" if p.get("parcel_id") and dap is not None else "")
    notes = ["Stage windows are the project's growth-stage table (days after planting). Tap a stage to ask what to do then: the answer comes from the TNAU documents."]
    if plant:
        notes.append(f"Planting date taken as {plant.strftime('%d %b %Y')} ({dap} days ago); dates move if the real planting date differs.")
    photo = None
    try:
        from app.steps import facts
        ph = facts._photo({"crop": {"name": crop}, "observed_issue": {"code": "healthy"}}, p.get("parcel_id") or "TM-00")
        photo = ph.get("url")
    except Exception:  # noqa: BLE001
        pass
    return {"id": "calendar", "title": title, "kind": "calendar", "steps": lines, "notes": notes, "warning": None, "photos": [], "raw_photo": photo,
            "videos": [], "contacts": [], "source": {"title": "Cropsy growth-stage table; advice per stage from TNAU", "url": "https://agritech.tnau.ac.in/"}, "extra_sources": [], "asks": asks}


# ── disease and pest gallery ─────────────────────────────────────────────────────────────────────────────────────────
_IDENT = re.compile(r"identify|what\s+is\s+(this|the)\s+(disease|pest|problem|insect)|common\s+(diseases?|pests?|problems?)|diseases?\s+(list|gallery|guide)|\b(diseases?|pests?)\s+of\s+\w+\s*\??\s*$|"
                    r"types?\s+of\s+(diseases?|pests?)|disease\s+and\s+pest|pest\s+and\s+disease|how\s+to\s+(spot|recognise|recognize)|என்ன\s*நோய்", re.IGNORECASE)


def identify_card(state: PipelineState) -> dict | None:
    crop = _crop_of(state)
    if not crop:
        return None
    try:
        cat = json.loads((config.DATA_DIR / "issue_catalog.json").read_text(encoding="utf-8"))
        items = json.loads((config.DATA_DIR / "images" / "manifest.json").read_text(encoding="utf-8")).get("items", [])
    except Exception:  # noqa: BLE001
        return None
    photos, lines = [], []
    from app.steps import refphotos
    for code, meta in cat.items():
        if code == "healthy" or meta.get("crop") not in (crop, "any"):
            continue
        pool = sorted((i for i in items if i.get("condition_code") == code and i.get("split") == "train"), key=lambda i: i["file"])
        sym = "; ".join((meta.get("symptoms") or [])[:3])
        lines.append(f"{meta['label']}: {sym or 'see photo'}" + ("" if (code in refphotos._EXTRA or any(i.get("condition_code") == code for i in items)) else " (no photo available yet)"))
        if code in refphotos._EXTRA:
            ex = refphotos._EXTRA[code]
            photos.append({"url": ex["url"], "credit": ex["source"], "page": "", "caption": f"{meta['label']}: {sym}"})
        elif pool:
            it = pool[len(pool) // 2]
            photos.append({"url": f"/images/{it['file']}", "credit": it.get("source") or "public dataset", "page": it.get("source_url") or "", "caption": f"{meta['label']}: {sym}"})
    if not lines:
        return None
    return {"id": "identify", "title": f"Common problems of {crop}: what they look like", "kind": "gallery", "steps": lines, "photos": photos[:6],
            "notes": ["Photos are reference images from public leaf-disease datasets, not your field. Symptoms are general descriptions: confirm with a TNAU KVK officer before treating.",
                      "To check your own plant, send a photo in the chat and Cropsy will match it."], "warning": None, "videos": [], "contacts": [],
            "source": {"title": "Public leaf-disease datasets (see photo credits); symptoms: general agronomy description", "url": "https://agritech.tnau.ac.in/"}, "extra_sources": [], "asks": []}


# ── income planner ───────────────────────────────────────────────────────────────────────────────────────────────────
_PLAN = re.compile(r"profit|income|earn|revenue|planner|cost\s+planner|how\s+much\s+(money|will\s+i\s+(get|make))|expected\s+(income|revenue|yield)|laabam|லாபம்|வருமானம்", re.IGNORECASE)


def planner_card(state: PipelineState) -> dict | None:
    p = state.parcel_context or {}
    if not p.get("parcel_id"):
        return None
    from app import advisory_extras as ex
    from app.steps import facts
    crop = (p.get("crop") or {}).get("name") or ""
    y = None
    try:
        y = ex.yield_outlook(p)
    except Exception:  # noqa: BLE001
        pass
    area_ha = float(p.get("area_ha") or 0)
    qty = None
    price = None
    note = []
    if y and str(y["unit"]).startswith("t/ha") and area_ha:
        qty = {k: round(float(y[k]) * 10 * area_ha, 1) for k in ("expected_low", "expected_mid", "expected_high")}     # tonnes per ha -> quintals for the parcel
        note.append(f"Expected production comes from this parcel's last three seasons ({y['expected_low']} to {y['expected_high']} {y['unit']}, sample data), times {area_ha} ha. It is an outlook, not a forecast.")
    elif y:
        note.append(f"This crop's yield is recorded as {y['unit']}, so enter your own expected quantity.")
    m = facts._msp(crop, {"mid": y["expected_mid"], "unit": y["unit"], "area_ha": area_ha} if y else None)
    if m.get("has_msp") and m.get("rows"):
        price = m["rows"][0]["msp_rs_per_quintal"]
        note.append(f"Price is pre-filled with the {m.get('year')} MSP (the government floor price): change it to today's mandi rate.")
    else:
        note.append(m.get("note", "No MSP: enter the mandi price you expect."))
    note.append("Costs are not guessed: enter your own seed, fertilizer, labour and other costs per acre. Nothing is saved or sent.")
    photo = None
    try:
        ph = facts._photo({"crop": {"name": crop}, "observed_issue": {"code": "healthy"}}, p["parcel_id"])
        photo = ph.get("url")
    except Exception:  # noqa: BLE001
        pass
    return {"id": "planner", "title": f"Income planner for {p['parcel_id']} ({crop})", "kind": "planner", "steps": [], "photos": [], "raw_photo": photo, "notes": note, "warning": None,
            "videos": [], "contacts": [], "asks": [], "extra_sources": [],
            "source": {"title": "Parcel yield history (sample data) and CCEA MSP 2024-25", "url": "https://pib.gov.in/"},
            "planner": {"crop": crop, "area_acre": round(area_ha * 2.471, 2), "qty": qty, "unit": "quintal" if qty else "units", "price": price}}



# ── priority (combined alerts) ───────────────────────────────────────────────────────────────────────────────────────
_PRIO = re.compile(r"which\s+(parcel|field|farm)s?.{0,25}(first|attention|urgent|need|worst|risk)|needs?\s+(my\s+)?attention|priorit|most\s+urgent|urgent\s+(parcel|field|alert)|"
                   r"(top|all|today'?s?|my)\s+alerts?|alerts?\s+(for|today|list)|biggest\s+risk|risk\s+(ranking|list)|attention\s+first", re.IGNORECASE)
_EMOJI = {"urgent": "URGENT", "high": "HIGH", "watch": "WATCH", "routine": "ROUTINE"}


def priority_card(state: PipelineState) -> dict | None:
    from app import priority
    p = state.parcel_context or {}
    pid = p.get("parcel_id")
    data = priority.ranked(pid, limit=1 if pid else 6)
    if not data["items"]:
        return None
    lines, asks = [], []
    for i, it in enumerate(data["items"], 1):
        reasons = "; ".join(f"{r['text']} [{r['source']}]" for r in it["reasons"])
        lines.append(f"{i}. {it['parcel_id']} ({it['crop']}, {it['stage']}): {_EMOJI[it['level']]}, score {it['score']}. {reasons}. Do: {it['action']}")
        if not pid and i <= 4:
            asks.append({"label": f"Ask about {it['parcel_id']}", "query": f"{it['parcel_id']} what should I do now?"})
    title = f"What needs attention first ({'parcel ' + pid if pid else 'top parcels in the village'})"
    notes = [data["how"], "Forecast source: " + data["forecast_source"] + "." + ("" if pid else " Select a parcel to see only its own list.")]
    photos = []
    try:
        from app.steps import facts
        from app.steps import tools as _tools
        _tools._load_parcels()
        for it in data["items"][:4]:
            pr = _tools._PARCEL_BY_ID.get(it["parcel_id"])
            ph = facts._photo(pr, it["parcel_id"]) if pr else {}
            if ph.get("url"):
                photos.append({"url": ph["url"], "credit": "parcel photo" if ph.get("kind") == "parcel" else "sample photo (dummy), public dataset", "page": "",
                               "caption": f"{it['parcel_id']} ({it['crop']}): " + ("photo supplied for this parcel" if ph.get("kind") == "parcel" else "sample photo of a similar plant, not this field")})
    except Exception:  # noqa: BLE001
        pass
    return {"id": "priority", "title": title, "kind": "priority", "steps": lines, "photos": photos, "notes": notes, "warning": None, "videos": [], "contacts": [], "extra_sources": [], "asks": asks,
            "source": {"title": "Fixed rules over forecast, satellite, crop stage, parcel record and history", "url": "https://agritech.tnau.ac.in/"}}


# ── knowledge base card ──────────────────────────────────────────────────────────────────────────────────────────────
_KB = re.compile(r"knowledge\s+base|what\s+(crops|topics)\s+(do|can)\s+you\s+(cover|know|advise)|what\s+do\s+you\s+(cover|know)|not\s+covered|knowledge\s+gaps?|your\s+sources|"
                 r"where\s+(do|does)\s+.{0,20}(information|advice|answers?)\s+come\s+from|how\s+reliable|can\s+i\s+trust|how\s+accurate", re.IGNORECASE)


MSP_RX = re.compile(r"\bmsp\b|minimum\s+support\s+price|support\s+price|ஆதார\s*விலை", re.IGNORECASE)
# a market-price question: Cropsy holds no live mandi prices, so it says so and points to the official price sources instead of letting a model improvise (it once answered "market price of chilli" with pest advice)
PRICE_RX = re.compile(r"\b(price|prices|mandi|agmarknet|enam)\b|market\s+(rate|price|value)|விலை|vilai|vilaiyum", re.IGNORECASE)


def msp_card(state: PipelineState) -> dict | None:
    """Government floor prices (CCEA 2024-25) from the data file; asked with no parcel. Not today's market rate."""
    import json
    from app import config
    try:
        rows = json.loads((config.DATA_DIR / "msp_2024_25.json").read_text(encoding="utf-8")).get("data", [])
    except Exception:  # noqa: BLE001
        return None
    q = f"{state.query} {state.normalized_query or ''}".lower()
    words = {"paddy": "paddy", "rice": "paddy", "nel": "paddy", "maize": "maize", "groundnut": "groundnut", "cotton": "cotton", "blackgram": "urad", "urad": "urad", "ulundu": "urad", "sugarcane": "sugar"}
    want = {v for k, v in words.items() if re.search(r"(?<![a-z])" + k + r"(?![a-z])", q)}
    pick = [r for r in rows if any(w in r["crop"].lower() for w in want)] if want else rows
    if not pick:
        return None
    steps = [f"{r['crop']}: Rs {r['msp_rs_per_quintal']} per quintal ({r.get('season', '')})" for r in pick[:14]]
    asked_price = bool(PRICE_RX.search(q)) and not MSP_RX.search(q)
    if asked_price:
        steps = ["Cropsy does not hold today's market (mandi) prices, so it will not quote one. For a live price, look at your nearest market's board, the Agmarknet site (agmarknet.gov.in) or the eNAM portal (enam.gov.in).",
                 *(["The government floor price (MSP, 2024-25) for the crop you named, for comparison: " + "; ".join(steps[:2])] if want and pick else [])]
    return {"id": "msp", "title": "Market price" if asked_price else "Minimum Support Price (MSP), 2024-25", "kind": "knowledge", "steps": steps, "photos": [],
            "notes": ["MSP is the government floor price, not today's market rate. It changes every year: check the current MSP and the mandi rate with your agriculture office or Agmarknet.",
                      "Source data file: CCEA / PIB India, 2024-25 season."], "warning": None, "videos": [], "contacts": [], "extra_sources": [], "asks": [],
            "source": {"title": "CCEA / PIB India: MSP 2024-25", "url": "https://pib.gov.in/"}}


INDEX_RX = re.compile(r"(?<![a-z])(ndvi|savi|evi|ndre|ndmi|ndwi)(?![a-z])[^.?]{0,40}(mean|meaning|explain|what is|what does|good|low|high|value)|(what|explain)[^.?]{0,25}(?<![a-z])(ndvi|savi|evi|ndre|ndmi|ndwi)(?![a-z])|"
                      r"which\s+(area|part|side|corner)\s+of\s+my\s+(field|farm|plot)|low\s+vegetation", re.IGNORECASE)
_INDEX_TEXT = {
    "ndvi": ("NDVI (greenness)", "Compares red and near-infrared light. Healthy green leaves reflect a lot of near-infrared. Bare soil is roughly 0.1 to 0.2, sparse or young crop 0.2 to 0.5, dense healthy crop 0.6 to 0.9."),
    "savi": ("SAVI", "Like NDVI but corrects for bright bare soil, so it is more reliable for young crops with gaps between plants."),
    "evi": ("EVI", "Like NDVI but less likely to max out over very dense canopy and less affected by haze."),
    "ndre": ("NDRE", "Uses the red-edge band, which reacts to leaf chlorophyll early, so it can show nitrogen or stress changes before NDVI does."),
    "ndmi": ("NDMI (moisture)", "Compares near-infrared and shortwave infrared, so it follows the water content of the leaves."),
    "ndwi": ("NDWI (water)", "Highlights open water and very wet surfaces, for example flooded fields, tanks and canals."),
}


SAT_Q = re.compile(r"(?<![a-z])(ndvi|savi|evi|ndre|ndmi|ndwi)(?![a-z])|satellite|vegetation|greenness|செயற்கைக்கோள்", re.IGNORECASE)
SPATIAL_Q = re.compile(r"which\s+(area|part|side|corner)|where\s+(is|are|should)|part\s+of\s+my\s+(field|farm|plot)|low\s+vegetation|uneven|patch|zone|inspect", re.IGNORECASE)
# a satellite question that asks for interpretation (health, why, where, compare, meaning) is answered by the model from the satellite evidence, not read off as a data lookup
INTERPRET_RX = re.compile(r"health|healthy|stress|why|which|where|inspect|check|decreas|dropp|falling|declin|compare|baseline|trend|mean|meaning|explain|what is|what does|poor|low\s+vegetation|irukka|nalama|ஆரோக்கிய", re.IGNORECASE)


def zones_card(state: PipelineState) -> dict | None:
    pid = state.parcel_id or (state.parcel_context or {}).get("parcel_id")
    if not pid:
        return None
    from app import field_analysis
    z = field_analysis.zones(pid)
    if not z["available"]:
        return {"id": "zones", "title": "Inside-the-field detail", "kind": "knowledge", "steps": [f"Not available for {pid}: {z['reason']}."], "photos": [], "notes": ["Cropsy will not guess which corner is low."],
                "warning": None, "videos": [], "contacts": [], "extra_sources": [], "asks": [], "source": {"title": "Sentinel-2 monthly composite, parcel pixels", "url": "https://earth-search.aws.element84.com/v1"}}
    lows = [c for c in z["cells"] if c["class"] == "lower"]
    highs = [c for c in z["cells"] if c["class"] == "higher"]
    steps = [f"{pid}, {z['month']} composite: parcel mean NDVI {z['parcel_mean']} over {z['n_valid']} clear pixels (about 11 m each)."]
    steps.append("Lower than the rest: " + "; ".join(f"{c['name']} {c['mean']} ({c['vs_parcel']})" for c in lows) if lows else "No part of the field is lower than the rest by more than the threshold.")
    if highs:
        steps.append("Higher than the rest: " + "; ".join(f"{c['name']} {c['mean']} (+{c['vs_parcel']})" for c in highs))
    return {"id": "zones", "title": f"Inside {pid}: where vegetation is lower", "kind": "knowledge", "steps": steps, "photos": [], "map_zones": pid,
            "notes": [z["caution"], "Method: " + z["method"]], "warning": None, "videos": [], "contacts": [], "extra_sources": [], "asks": [],
            "source": {"title": "Sentinel-2 L2A monthly composite, clipped to the parcel boundary", "url": "https://earth-search.aws.element84.com/v1"}}


def index_card(state: PipelineState) -> dict | None:
    """What a satellite index means, the parcel's own latest value, and what NOT to conclude from it. Plain facts, no model."""
    q = f"{state.query} {state.normalized_query or ''}".lower()
    which = [k for k in _INDEX_TEXT if re.search(r"(?<![a-z])" + k + r"(?![a-z])", q)] or ["ndvi"]
    steps = [f"{_INDEX_TEXT[k][0]}: {_INDEX_TEXT[k][1]}" for k in which]
    notes = ["A low or falling index means 'go and look', not 'there is a disease or a nutrient shortage'. Young crops, harvest, flooding, shadow, cloud and a different crop stage can all lower it.",
             "Detail inside a field: each satellite pixel is about 11 m across, so a 1 ha field has only about 100 pixels. Cropsy can split a field into a 3 x 3 grid of its own pixels and show which part is lower; it cannot see anything smaller, and a very small or cloudy parcel may not have enough clear pixels.",
             "General remote-sensing knowledge, not a TNAU figure. Parcel and crop details in this demo are dummy; the satellite values are real."]
    pid = state.parcel_id or (state.parcel_context or {}).get("parcel_id")
    try:
        from app.steps import tools
        sat = tools._load_satellite()
        e = ((sat.get("parcels") or {}).get(pid)) if pid and sat else None
        if e:
            ch = e.get("change")
            steps.append(f"{pid}, latest satellite scene ({e.get('latest_date')}), mean over the parcel: NDVI {e.get('latest_ndvi')}; usual level before that {e.get('baseline_ndvi')}; change {ch}; status {e.get('status')}.")
    except Exception:  # noqa: BLE001
        pass
    return {"id": "index", "title": "What the satellite index means", "kind": "knowledge", "steps": steps, "photos": [], "notes": notes, "warning": None, "videos": [], "contacts": [],
            "extra_sources": [], "asks": [], "source": {"title": "Sentinel-2 vegetation indices (general remote-sensing knowledge)", "url": "https://custom-scripts.sentinel-hub.com/sentinel-2/ndvi/"}}


def kb_card(state: PipelineState) -> dict | None:
    from app import knowledge_info
    k = knowledge_info.summary()
    lines = []
    for r in k["crops"]:
        miss = ("; not covered: " + ", ".join(r["missing_topics"])) if r["missing_topics"] else ""
        lines.append(f"{r['crop']}: {r['passages']} passages, {r['depth'].upper()}{miss}")
    src = "; ".join(f"{s['title']} ({s.get('organization', '')}, {s.get('year', '')}): {s['passages']} passages" for s in k["sources"])
    notes = ["Sources: " + src + ".", "Built: " + str(k["built"]) + ". " + "Where a crop is THIN, answers get a lower confidence label and should be checked with a TNAU officer."] + k["not_covered"]
    return {"id": "kb", "title": "What Cropsy's advisory documents cover", "kind": "knowledge", "steps": lines, "photos": ["k_paddy1"], "notes": notes, "warning": None, "videos": [], "contacts": [],
            "extra_sources": [], "asks": [], "source": {"title": "TNAU Crop Production Guides 2020 (Agriculture and Horticulture)", "url": "https://agritech.tnau.ac.in/"}}


# ── nearest KVK and soil labs, with directions ───────────────────────────────────────────────────────────────────────
OFFICES_RX = re.compile(r"\bkvk\b|krishi\s+vigyan|soil\s+(testing\s+)?(lab|laboratory)|(lab|laboratory).{0,20}(soil|test)|where\s+(can|do|to|should)\s+(i|we)?\s*(get|test|check|take).{0,25}soil|"
                        r"nearest\s+(lab|laboratory|agri\w*|office|krishi)|agriculture\s+(office|department)\s+(near|address|contact)|(how|way)\s+to\s+(reach|go)|directions?\s+to|route\s+to|"
                        r"extension\s+(office|centre|center)|\bviavasaya\b|விவசாய\s*(அலுவலகம்|ஆய்வகம்)|மண்\s*பரிசோதனை\s*(நிலையம்|ஆய்வகம்)", re.IGNORECASE)


def offices_card(state: PipelineState) -> dict | None:
    import math
    try:
        d = json.loads((config.DATA_DIR / "offices.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    p = state.parcel_context or {}
    loc = p.get("location") or {}
    if loc.get("lat") is not None:
        o_lat, o_lon, o_name = float(loc["lat"]), float(loc["lon"]), f"parcel {p.get('parcel_id')}"
    else:
        o_lat, o_lon, o_name = d["village"]["lat"], d["village"]["lon"], "Then Malai"
    q = f"{state.query} {state.normalized_query or ''}".lower()
    want_soil = bool(re.search(r"soil|lab|மண்", q))
    want_kvk = bool(re.search(r"kvk|krishi|vigyan|extension", q))
    items = []
    for o in d["items"]:
        la1, lo1, la2, lo2 = map(math.radians, (o_lat, o_lon, o["lat"], o["lon"]))
        a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        km = round(6371 * 2 * math.asin(math.sqrt(a)))
        items.append({**o, "km": km, "directions": f"https://www.google.com/maps/dir/?api=1&origin={o_lat},{o_lon}&destination={o['lat']},{o['lon']}&travelmode=driving"})
    if want_soil and not want_kvk:
        items = [o for o in items if o["kind"] == "soil_lab"] or items
    elif want_kvk and not want_soil:
        items = [o for o in items if o["kind"] == "kvk"] or items
    items.sort(key=lambda o: o["km"])
    lines = [f"{o['name']}: {o['area']}. About {o['km']} km from {o_name} in a straight line (the road is longer). {o['services']}" for o in items]
    return {"id": "offices", "title": "Nearest KVK and soil testing labs", "kind": "offices", "steps": lines, "photos": [], "notes": [d["note"], "The Directions buttons open Google Maps from " + o_name + "; the pin is approximate, so confirm the exact address by phone or at the block agriculture office first."],
            "warning": None, "videos": [], "contacts": [], "extra_sources": [{"title": o["source"]["title"], "url": o["source"]["url"]} for o in items[:1]], "asks": [{"label": "How to take a soil sample", "query": "How to take a soil sample?"}],
            "source": {"title": "TNAU Agritech: KVK and soil testing labs in Tamil Nadu", "url": "https://agritech.tnau.ac.in/agriculture/agri_soil_testinglabs.html"},
            "offices": {"origin": {"name": o_name, "lat": o_lat, "lon": o_lon}, "items": [{"name": o["name"], "kind": o["kind"], "lat": o["lat"], "lon": o["lon"], "km": o["km"], "directions": o["directions"], "precision": o["precision"]} for o in items]}}


# ── village counts ───────────────────────────────────────────────────────────────────────────────────────────────────
_VILLAGE = re.compile(r"how\s+many\s+(parcels|fields|farms|plots)|number\s+of\s+(parcels|fields|farms|plots)|total\s+(area|acreage)|which\s+parcels\s+(grow|have|are\s+growing)|"
                      r"list\s+(of\s+)?(all\s+)?(parcels|fields)", re.IGNORECASE)


def village_card(state: PipelineState) -> dict | None:
    from app.steps import tools
    tools._load_parcels()
    ps = tools._PARCELS
    crop = None
    q = f"{state.query} {state.normalized_query or ''}".lower()
    for alias, c in config.CROP_ALIASES.items():
        if alias in q:
            crop = c.capitalize()
    for c in config.CROPS:
        if re.search(rf"\b{c.lower()}\b", q):
            crop = c
    by: dict[str, list] = {}
    for p in ps:
        by.setdefault(p["crop"]["name"], []).append(p)
    rows = [f"{c}: {len(v)} parcels, {sum(float(x.get('area_ha') or 0) for x in v):.2f} ha" for c, v in sorted(by.items(), key=lambda kv: -len(kv[1]))]
    total_ha = sum(float(p.get("area_ha") or 0) for p in ps)
    if crop and crop in by:
        v = by[crop]
        msg = f"{len(v)} parcels in Then Malai grow {crop}, with a total area of {sum(float(x.get('area_ha') or 0) for x in v):.2f} ha. Parcels: " + ", ".join(x["parcel_id"] for x in v) + "."
    else:
        msg = f"Then Malai has {len(ps)} parcels with a total area of {total_ha:.2f} ha."
    return {"id": "village", "title": "Then Malai parcels at a glance", "kind": "knowledge", "message": msg, "steps": rows, "photos": [], "notes": ["Counts come from the parcel records (dummy crop data)."],
            "warning": None, "videos": [], "contacts": [], "extra_sources": [], "asks": [], "source": {"title": "Then Malai parcel records", "url": "https://agritech.tnau.ac.in/"}}


# ── village spread-risk scan ─────────────────────────────────────────────────────────────────────────────────────────
_SPREAD = re.compile(r"epidemic|village\s+scan|spread\s+(forecast|risk|map|scan|prediction)|downwind\s+(parcels|fields|farms)|which\s+(other\s+)?(parcels|fields|farms)\s+(will|may|might|could|are\s+at\s+risk)|"
                     r"(neighbou?r\w*|nearby)\s+(parcels|fields|farms).{0,25}(risk|infect)|will\s+(it|the\s+disease|blast|rust)\s+spread|predict.{0,20}(spread|infect)|பரவ", re.IGNORECASE)


def spread_card(state: PipelineState, photo_code: str | None = None) -> dict | None:
    from app import spread, spread_api
    p = state.parcel_context or {}
    pid, chosen_note = None, ""
    if photo_code and p.get("parcel_id"):
        pid = p["parcel_id"]                                 # a photo of this parcel matched a wind-borne disease: scan from here
    elif (p.get("observed_issue") or {}).get("code") in spread.AIRBORNE:
        pid = p["parcel_id"]
    srcs = spread_api.sources()["items"]
    if not srcs:
        return None
    named = re.search(r"tm\s?-?\s?(\d{1,3})", f"{state.query} {state.normalized_query or ''}".lower())
    if named and not pid:                                   # "...from TM-31": use that parcel if its recorded problem is a wind-borne disease
        cand = f"TM-{int(named.group(1)):02d}"
        if cand in {s["parcel_id"] for s in srcs}:
            pid = cand
    if not pid:
        pid = srcs[0]["parcel_id"]
        chosen_note = f"No infected parcel was selected, so this shows {pid}: the parcel with a recorded wind-borne disease that has the most susceptible neighbours in spore reach (dummy records)."
    res = spread.forecast(pid, disease_code=photo_code)
    if photo_code:
        chosen_note = "This scan starts from your photo: the nearest reference photos matched this disease. A photo match is a hint, not a confirmed diagnosis; if it is right, these are the parcels at risk."
    top = [r for r in res["parcels"] if r["crop"] == res["source"]["crop"] and r["distance_m"] <= res["disease"]["max_m"]]
    lines = [f"1. Spatial query: {len(res['parcels']) + 1} parcels checked; {len(top)} {res['source']['crop'].lower()} parcels lie within {res['disease']['max_m']} m of {pid}. Distances and bearings recomputed a second way.",
             f"2. Wind: {res['wind']['source']}; mean {res['wind']['mean_speed_kmh']} km/h from the {res['wind']['from_compass']} (air moves toward the {res['wind']['toward_compass']}).",
             f"3. Disease biology: {res['disease']['label']}; weather window {res['disease']['weather_window']}; {res['weather']['favourable_hours']} of {res['weather']['of']} forecast hours are favourable. Each parameter is tagged TNAU or assumption.",
             f"4. Scoring: exposure index 0 to 100 for each susceptible parcel; {res['summary']['red']} red, {res['summary']['amber']} amber, {res['summary']['watch']} watch.",
             "5. Alert: press the button to write the village notice in Tamil and English (one small model call)."]
    notes = ([chosen_note] if chosen_note else []) + res["data_quality"] + res["notes"]
    return {"id": "spread", "title": f"Village spread-risk scan from {pid}: {res['source']['disease']}", "kind": "spread", "steps": lines, "photos": [], "notes": notes, "warning": None,
            "videos": [], "contacts": [], "extra_sources": [], "asks": [{"label": f"Scan from {s['parcel_id']} ({s['issue']})", "query": f"{s['parcel_id']} village spread risk scan"} for s in srcs[:4] if s["parcel_id"] != pid],
            "source": {"title": "TNAU Agritech (qualitative) and model assumptions; see the evidence list", "url": "https://agritech.tnau.ac.in/"}, "spread": res, "spread_sources": srcs[:8]}


# ── counterfactual regret ────────────────────────────────────────────────────────────────────────────────────────────
_REGRET = re.compile(r"\bregret\b|could\s+(this|it|that)\s+have\s+been\s+(prevented|avoided|stopped)|\bpreventable\b|missed\s+(window|moment|chance)|when\s+did\s+(the\s+)?(infection|disease|blast|rust|sigatoka)\s+(start|begin|happen|come)|"
                     r"infection\s+window|what\s+should\s+i\s+have\s+done|time\s*line\s+of\s+(the\s+)?(infection|disease)", re.IGNORECASE)


def regret_card(state: PipelineState) -> dict | None:
    from app import regret, spread, spread_api
    p = state.parcel_context or {}
    pid = p["parcel_id"] if (p.get("observed_issue") or {}).get("code") in spread.AIRBORNE else None
    srcs = spread_api.sources()["items"]
    if not srcs:
        return None
    named = re.search(r"tm\s?-?\s?(\d{1,3})", f"{state.query} {state.normalized_query or ''}".lower())
    if named and not pid:
        cand = f"TM-{int(named.group(1)):02d}"
        if cand in {s["parcel_id"] for s in srcs}:
            pid = cand
    note = ""
    res = None
    if pid:
        res = regret.analyse(pid)
    else:                                                    # no infected parcel chosen: take the first one whose weather history gives a plausible window
        for s in srcs:
            r = regret.analyse(s["parcel_id"])
            if r.get("available") and r["reconstruction"]["best"]:
                res, pid = r, s["parcel_id"]
                break
        if res is None:
            pid = srcs[0]["parcel_id"]
            res = regret.analyse(pid)
        note = f"No infected parcel was selected, so this shows {pid}: a parcel with a recorded wind-borne disease whose weather history contains a plausible infection window (dummy records)."
    if not res.get("available"):
        return {"id": "regret", "title": "Infection-window reconstruction unavailable", "kind": "knowledge", "message": res["message"], "steps": [], "photos": [], "notes": [], "warning": None,
                "videos": [], "contacts": [], "extra_sources": [], "asks": [], "source": {"title": "Cropsy", "url": "https://agritech.tnau.ac.in/"}}
    rc = res["reconstruction"]
    lines = [f"1. Disease biology: {res['source']['disease']}; weather window {res['params']['t_low']:g}-{res['params']['t_high']:g} C, humidity at least {res['params']['rh_min']:g}%, {res['params']['min_hours']}+ hours in a row (tagged assumption).",
             f"2. Weather history: {res['history']['hours']} hours of model-analysed weather for this point ({res['history']['start'][:10]} to {res['history']['end'][:10]}).",
             f"3. Reconstruction: symptoms noted {rc['symptom_noted_days_ago']:g} days ago; with a {res['params']['latency_min']:g}-{res['params']['latency_max']:g} day latency the infection fell between {rc['expected_infection_from'][:10]} and {rc['expected_infection_to'][:10]}. " + rc["statement"],
             "4. Regret: potential loss = area x the parcel's own yield x price x loss share; enter your cost of prevention below (no cost is assumed).",
             f"5. Scan: {len(res['twins'])} {res['source']['crop'].lower()} parcels checked for the next 72 hours: {res['summary']['act_now']} act now, {res['summary']['prepare']} prepare, {res['summary']['monitor']} monitor.",
             "6. Verifier: ACT NOW or PREPARE only if temperature, humidity and crop stage all pass; any miss is downgraded to MONITOR.",
             "7. Brief: press the button for the Tamil and English notice (one small model call)."]
    return {"id": "regret", "title": f"Counterfactual regret for {pid}: {res['source']['disease']}", "kind": "regret", "steps": lines, "photos": [], "notes": ([note] if note else []) + res["data_quality"], "warning": None,
            "videos": [], "contacts": [], "extra_sources": [], "asks": [{"label": f"Reconstruct for {s['parcel_id']} ({s['issue']})", "query": f"{s['parcel_id']} infection window regret"} for s in srcs[:4] if s["parcel_id"] != pid],
            "source": {"title": "TNAU Agritech (qualitative) and model assumptions; see the evidence list", "url": "https://agritech.tnau.ac.in/"}, "regret": res, "spread_sources": srcs[:10]}


# ── entry points used by guides.py ───────────────────────────────────────────────────────────────────────────────────
def dynamic_only(state: PipelineState) -> list[dict]:
    """Questions these cards answer completely (no model)."""
    q = f"{state.query} {state.normalized_query or ''}".lower()
    if _CAL.search(q):
        c = calendar_card(state)
        if c:
            return [c]
    if _PLAN.search(q):
        c = planner_card(state)
        if c:
            return [c]
    if _IDENT.search(q):
        c = identify_card(state)
        if c:
            return [c]
    from app.steps import guides_extra as gx
    if gx.PEST_CHECK_RX.search(q):
        c = gx.pesticide_card(state)
        if c:
            return [c]
    if gx.VARIETY_GUIDE_RX.search(q):
        c = gx.variety_card(state)
        if c:
            return [c]
    if gx.HARVEST_GUIDE_RX.search(q):
        c = gx.harvest_card(state)
        if c:
            return [c]
    if _VILLAGE.search(q) and not (state.parcel_id or state.parcel_context):
        c = village_card(state)
        if c:
            return [c]
    if _REGRET.search(q):
        c = regret_card(state)
        if c:
            return [c]
    if _SPREAD.search(q):
        c = spread_card(state)
        if c:
            return [c]
    if (MSP_RX.search(q) or PRICE_RX.search(q)) and not (state.parcel_id or state.parcel_context):
        c = msp_card(state)
        if c:
            return [c]
    if _KB.search(q):
        c = kb_card(state)
        if c:
            return [c]
    if _PRIO.search(q):
        c = priority_card(state)
        if c:
            return [c]
    if _WEATHER_SHORT.search(q) and len(q.split()) <= 8 and not _WEATHER_OTHER.search(q):      # "will it rain?" on its own: show the forecast and what to do
        c = weather_card(state)
        if c:
            return [c]
    if _WEATHER_EXPLICIT.search(q):
        c = weather_card(state)
        if c:
            return [c]
    return []


def dynamic_extra(state: PipelineState) -> list[dict]:
    """Cards added under a normal answer."""
    q = f"{state.query} {state.normalized_query or ''}".lower()
    out: list[dict] = []
    if state.image_bytes and state.parcel_context:                  # photo of a parcel matched a wind-borne disease: offer the village scan
        try:
            from app import spread
            from app.steps import caption as _cap
            code, _label, crop = _cap._top_condition(state)
            if code in spread.AIRBORNE and crop == (state.parcel_context.get("crop") or {}).get("name"):
                c = spread_card(state, photo_code=code)
                if c:
                    out.append(c)
        except Exception:  # noqa: BLE001
            pass
    if _WEATHER_ANY.search(q) and (state.parcel_context or state.parcel_id):
        c = weather_card(state)
        if c:
            out.append(c)
    if INDEX_RX.search(q) or SAT_Q.search(q):
        c = index_card(state)
        if c:
            out.append(c)
        z = zones_card(state) if SPATIAL_Q.search(q) else None
        if z:
            out.append(z)
    from app import pesticides
    from app.steps import guides_extra as gx
    if pesticides.mentioned(q):
        c = gx.pesticide_card(state)
        if c:
            out.append(c)
    if gx.VARIETY_RX.search(q):
        c = gx.variety_card(state)
        if c:
            out.append(c)
    if gx.HARVEST_RX.search(q):
        c = gx.harvest_card(state)
        if c:
            out.append(c)
    return out[:2]
