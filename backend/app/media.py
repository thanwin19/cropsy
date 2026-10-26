"""media.py: decide which visual, if any, helps a finished answer. Runs AFTER the text answer (POST /api/media), so the answer never waits for it.

The existing small model (Nova Micro) is shown the question, the answer and a CLOSED menu of what Cropsy actually has:
  diagrams drawn in the app, licensed photographs in data/images/fertilizer (with their credits), a 7-day weather chart for a parcel, and a video search.
It can only choose from that menu; its reply is validated and anything outside the menu is dropped. If the model is unavailable, simple rules choose.
No image is generated, no photo is claimed to show the farmer's own field, and no specific video is named: the video is always a labelled search.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from app import config

log = logging.getLogger(__name__)

DIAGRAMS = {
    "ph_scale": "soil pH scale (acidic to alkaline), for soil reaction, pH, lime or gypsum questions",
    "compost_bed": "vermicompost bed cross-section",
    "compost_heap": "compost or farmyard-manure heap",
    "drip": "drip irrigation layout",
    "spacing": "plant spacing in rows",
    "growth_stages": "generic crop growth stages from seed to harvest, for sowing time, crop duration or stage questions",
    "npk": "what nitrogen, phosphorus and potassium do for a plant, for fertilizer and nutrient questions",
    "deficiency_table": "table of nutrient-deficiency leaf symptoms (nitrogen, phosphorus, potassium, magnesium, zinc, iron), for questions about yellow leaves, deficiency or symptoms",
    "plant_parts": "labelled parts of a plant (roots, stem, leaves, flower, fruit), for plant anatomy questions",
    "insect_cycle": "insect life cycle (egg, larva, pupa, adult), for pest life-cycle or pest-stage questions",
}

# photographs Cropsy holds (data/images/fertilizer), each with a plain label of what it actually shows (checked by eye) and its licence in credits.json
PHOTOS = {
    "urea": "Urea fertilizer granules", "dap": "DAP fertilizer granules", "fym": "Farmyard manure", "dungheap": "Dung heap for manure",
    "vermicompost": "Vermicompost", "wormbed": "Worm bed for vermicompost", "topdress": "Fertilizer being applied by hand (top dressing)",
    "k_drip1": "Drip lines at banana plants", "k_drip2": "Drip irrigation tubing", "k_soillab": "A soil-testing laboratory",
    "k_soil1": "Taking a soil sample in the field", "k_spray": "A boom sprayer working in a field", "k_paddy1": "Transplanting paddy in a flooded field",
    "w_rain": "Water-filled terraced paddy field",
    # pests and traps (data/images/pests, from Wikimedia Commons; labels say what the photo shows, not that it is the farmer's pest)
    "aphids": "Aphids on a maize leaf", "whitefly": "Silverleaf whitefly adult (carries leaf curl virus)", "rhino_beetle": "Coconut rhinoceros beetle",
    "pheromone_trap": "A pheromone trap in a rice field", "cane_borer_moth": "Sugarcane borer moth (Diatraea saccharalis, an American species; Indian cane borers look different)",
    "thrips": "Thrips on a leaf", "mealybug": "Mealybug", "rice_stem_borer": "Rice yellow stem borer moth", "trichogramma": "Trichogramma wasp on eggs (the egg parasitoid used in biological control)",
}


def _credits() -> dict:
    out: dict = {}
    for sub in ("fertilizer", "pests"):
        try:
            out.update(json.loads((config.DATA_DIR / "images" / sub / "credits.json").read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            pass
    return out


def photo_item(pid: str) -> dict | None:
    c = _credits().get(pid)
    f = c.get("file") if c else None
    if not f or not (config.DATA_DIR / "images" / f).exists() or pid not in PHOTOS:   # a photo that is not on disk is never offered
        return None
    return {"id": pid, "url": f"/images/{f}", "label": PHOTOS[pid], "credit": f"{c.get('author', 'unknown')}, {c.get('license', '')} (Wikimedia Commons)",
            "page": c.get("page")}


_PROMPT = """You choose a small visual to go under a farming answer. Reply with ONLY JSON: {{"diagram": <id or null>, "photo": <id or null>, "weather_chart": <true|false>, "video": <true|false>, "video_query": "<=6 words"}}.
Rules: choose a visual only if it truly helps THIS answer; null / false is a good answer. At most one diagram and one photo. weather_chart only for weather, rain or irrigation-timing questions. video true only for a how-to or practical question; video_query is plain search words, no URL.
DIAGRAMS:
{diagrams}
PHOTOS:
{photos}
QUESTION: {q}
ANSWER: {a}"""


def _rules(q: str, a: str) -> dict:
    t = f"{q}".lower()
    d = None
    if re.search(r"deficien|yellow(ing)? leaves|leaf symptom|nutrient symptom", t):
        d = "deficiency_table"
    elif re.search(r"parts of (a )?plant|plant anatomy|plant parts", t):
        d = "plant_parts"
    elif re.search(r"life ?cycle|stages of (the )?(pest|insect|moth|beetle|borer|armyworm)", t):
        d = "insect_cycle"
    if d is None:
        if re.search(r"\bsoil\s*ph\b|\bph\s*\d|alkalin|acidic|gypsum|lime", t):
            d = "ph_scale"
        elif re.search(r"vermi|earthworm", t):
            d = "compost_bed"
        elif re.search(r"compost|farmyard|\bfym\b|manure", t):
            d = "compost_heap"
        elif re.search(r"\bdrip\b|fertigation|emitter", t):
            d = "drip"
        elif re.search(r"spacing|row to row|plant to plant", t):
            d = "spacing"
        elif re.search(r"sowing|planting time|duration|growth stage|season|when to sow", t):
            d = "growth_stages"
        elif re.search(r"fertili[sz]er|nutrient|\burea\b|\bdap\b|potash|npk|deficien", t):
            d = "npk"
    photo = next((p for k, p in (("urea", "urea"), ("dap", "dap"), ("fym", "fym"), ("vermi", "vermicompost"), ("drip", "k_drip1"), ("soil test", "k_soillab"), ("spray", "k_spray"), ("paddy|rice", "k_paddy1")) if re.search(k, t)), None)
    pest = next((p for k, p in (("aphid", "aphids"), ("whitefly|white fly|leaf curl", "whitefly"), ("rhinoceros", "rhino_beetle"), ("pheromone", "pheromone_trap"), ("stem borer.*sugarcane|sugarcane.*borer|cane borer", "cane_borer_moth"), ("thrips", "thrips"), ("mealy", "mealybug"), ("rice.*stem borer|stem borer.*(rice|paddy)", "rice_stem_borer"), ("trichogramma|egg parasit", "trichogramma")) if re.search(k, t)), None)
    photo = pest or photo
    return {"diagram": d, "photo": photo, "weather_chart": bool(re.search(r"\brain|weather|forecast|irrigat", t)),
            "video": bool(re.search(r"how to|how do i|make|prepare|control|manage|disease|pest|borer|blight|rust|wilt|rot", t)), "video_query": ""}


def plan(query: str, answer: str, crop: str | None = None) -> dict:
    q, a = (query or "")[:300], (answer or "")[:500]
    raw: dict = {}
    by = "model"
    try:
        from app.models import bedrock
        p = _PROMPT.format(diagrams="\n".join(f"- {k}: {v}" for k, v in DIAGRAMS.items()), photos="\n".join(f"- {k}: {v}" for k, v in PHOTOS.items()), q=q, a=a)
        text, _t, _l = bedrock.invoke_text(config.MODEL_NOVA_MICRO, p, max_tokens=120)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        raw = json.loads(m.group()) if m else {}
    except Exception as e:  # noqa: BLE001
        log.warning("media planner unavailable (%s): rules used", e)
        raw = _rules(q, a)
        by = "rules"
    rules = _rules(q, a)                           # the model is careful and often says "none": a clear keyword match still earns its visual
    diagram = raw.get("diagram") if raw.get("diagram") in DIAGRAMS else None
    need = {"compost_bed": r"vermi|worm", "drip": r"\bdrip\b|fertigation|emitter", "spacing": r"spacing|row to row|plant to plant|apart|between rows", "ph_scale": r"\bph\b|alkalin|acid|lime|gypsum|saline|sodic"}
    if diagram in need and not re.search(need[diagram], q, re.I):       # a diagram must match what was asked
        diagram = None
    diagram = diagram or rules["diagram"]
    pid = raw.get("photo") if isinstance(raw.get("photo"), str) else None
    if pid and pid != rules["photo"] and not ((_tokens(PHOTOS.get(pid, "")) - _WEAK) & _tokens(q)):
        pid = None                                      # the model's pick must be named in the question (or be the keyword match): "pest and disease control" is not a whitefly question
    photo = photo_item(pid) if pid else None
    photo = photo or (photo_item(rules["photo"]) if rules["photo"] and rules["diagram"] in (None, "npk", "compost_heap", "compost_bed", "drip") else None)
    raw["video"] = bool(raw.get("video")) or rules["video"]
    raw["weather_chart"] = bool(raw.get("weather_chart")) or rules["weather_chart"]
    if not raw.get("video_query"):
        raw["video_query"] = ""
    vq = re.sub(r"[^\w\s஀-௿-]", " ", re.sub(r"(https?:|www\.)\S*", " ", str(raw.get("video_query") or "")))[:60].strip()
    lib = library_photos(q, crop)
    ext = None
    if not lib and not photo and not diagram and re.search(r"look|photo|picture|image|symptom|damage|pest|disease|deficien|machine|equipment|trap|seedling|nursery|harvest", q, re.I):
        ext = external_photo(q, crop)               # only for questions where a picture clearly helps, and only when nothing local fits
    return {"diagram": diagram, "photo": photo, "photos": lib, "external": ({"url": f"/images/{ext['file']}", "label": ext["label"], "credit": ext["credit"], "page": ext.get("page"),
            "note": "Matched to your question by its title; not checked by Cropsy."} if ext else None),
            "videos": tnau_videos(q, crop), "weather_chart": bool(raw.get("weather_chart")), "video": bool(raw.get("video")), "video_query": vq, "crop": crop, "by": by}


def weather_series(parcel_id: str | None) -> list[dict]:
    """The 7-day forecast Cropsy already uses for a parcel (live Open-Meteo or the stored CSV); empty if there is no parcel."""
    if not parcel_id:
        return []
    try:
        from app.schemas import PipelineState
        from app.steps import tools
        s = PipelineState(query="weather", parcel_id=parcel_id)
        s = tools.parcel_lookup(s)
        s = tools.weather(s)
        rows = (s.weather_data or {}).get("forecast") or []
        return [{"date": r.get("date"), "rain_mm": r.get("rain_mm"), "tmax_c": r.get("tmax_c"), "tmin_c": r.get("tmin_c")} for r in rows[:7]
                if r.get("date") and r.get("rain_mm") is not None]
    except Exception:  # noqa: BLE001
        return []


_RATING = r"(very low|low|medium|moderate|high|very high|normal|adequate|sufficient|deficient|acidic|neutral|alkaline|saline)"
_ROW = re.compile(rf"^\s*([A-Za-z][A-Za-z0-9 ()/%.\-]{{1,38}}?)\s*[:=\-]?\s+(\d+(?:\.\d+)?)\s*((?:kg/ha|mg/kg|t/ha|q/ha|ds/m|dsm|ppm|meq|%|kg|g|ml|cm|ha|mm)(?![A-Za-z]))?\s*(?:[(\-]?\s*{_RATING}\)?)?\s*$", re.IGNORECASE)


_NUM_LINE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*((?:kg/ha|mg/kg|t/ha|q/ha|ds/m|dsm|ppm|meq|%|kg|g|ml|cm|ha|mm)(?![A-Za-z]))?\s*$", re.IGNORECASE)
_RATING_LINE = re.compile(rf"^\s*{_RATING}\s*$", re.IGNORECASE)
_SKIP = ("survey", "page", "date", "no", "sl", "year", "parameter", "value", "rating", "report")


def doc_values(text: str | None) -> list[dict]:
    """Rows such as 'Nitrogen (kg/ha) 180 Low' read from a document's text, for a readable values list. Two layouts are understood: a whole row on one line, and a
    table whose cells came out on separate lines (name, then value, then rating). Nothing is added or converted: the numbers are exactly those in the text."""
    out: list[dict] = []
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    i = 0
    while i < len(lines):
        ln = re.sub(r"^\[page \d+\]\s*", "", lines[i])
        m = _ROW.match(ln)
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip(" :-")
            if len(name) >= 2 and name.lower() not in _SKIP:
                rate = None if m.group(4) or i + 1 >= len(lines) else _RATING_LINE.match(lines[i + 1])        # the rating may sit on the next line
                out.append({"name": name, "value": m.group(2), "unit": (m.group(3) or "").strip(), "rating": (m.group(4) or (rate.group(1) if rate else "")).lower() or None})
                i += 2 if rate else 1
                continue
            i += 1
            continue
        nxt = _NUM_LINE.match(lines[i + 1]) if i + 1 < len(lines) else None
        mm = re.match(r"^(.*?)\s+(\d+(?:\.\d+)?)$", ln)                      # "Nitrogen (kg/ha) 180" with the rating on the next line
        if nxt and re.match(r"^[A-Za-z][A-Za-z0-9 ()/%.\-]{1,38}$", ln) and ln.lower() not in _SKIP:
            rate = _RATING_LINE.match(lines[i + 2]) if i + 2 < len(lines) else None
            out.append({"name": ln, "value": nxt.group(1), "unit": (nxt.group(2) or "").strip(), "rating": rate.group(1).lower() if rate else None})
            i += 3 if rate else 2
            continue
        if mm and re.match(r"^[A-Za-z][A-Za-z0-9 ()/%.\-]{1,38}$", mm.group(1)) and mm.group(1).lower() not in _SKIP:
            rate = _RATING_LINE.match(lines[i + 1]) if i + 1 < len(lines) else None
            out.append({"name": mm.group(1), "value": mm.group(2), "unit": "", "rating": rate.group(1).lower() if rate else None})
            i += 2 if rate else 1
            continue
        i += 1
    return out[:12] if len(out) >= 2 else []


# ── the local library (data/images/library.json, built by scripts/build_image_library.py and checked by eye) ─────────────────────────────────
_STOP = set("the a an of for in on to and or is are what how why when which do does can i my me your with from this that it its at by be as about into over under use using crop crops plant plants field look looks like make time best tips need needs".split())
_WEAK = {"irrigation", "water", "soil", "harvest", "management", "control", "cultivation", "production", "method", "methods", "disease", "pest", "pests", "diseases", "problem"}
_GENERIC = {"damage", "symptom", "symptoms", "picture", "pictures", "photo", "photos", "image", "images", "show", "dead", "heart", "control", "management", "cultivation", "production", "method", "methods", "problem", "problems", "tips", "water", "soil"}
_CROPS = {"rice", "paddy", "wheat", "maize", "ragi", "sorghum", "cumbu", "bajra", "millet", "groundnut", "sesame", "castor", "sunflower", "soybean", "cowpea", "gram", "redgram", "blackgram", "greengram", "horsegram", "turmeric", "chilli", "tomato", "brinjal", "onion", "okra", "sugarcane", "coconut", "banana", "cotton", "mango", "potato", "cabbage", "cauliflower", "carrot", "beans", "tuberose", "vegetable", "vegetables"}
_PROBLEM = re.compile(r"control|disease|pest|borer|blight|wilt|rot\b|virus|worm|insect|spray|deficien|damage|mite|weevil|beetle|caterpillar|armyworm|whitefly|aphid|thrips|mildew|bollworm|symptom", re.I)
_PROBLEM_TOPICS = {"fall_armyworm", "pod_borer", "leaf_folder", "brinjal_borer", "pink_bollworm", "red_palm_weevil", "coconut_mite", "powdery_mildew", "bacterial_blight", "banana_bunchy_top",
                   "panama_wilt", "n_deficiency", "p_deficiency", "k_deficiency", "zinc_deficiency", "earthworm_pest"}
_CROP_TOPICS = {"wheat_field", "ragi", "sorghum", "pearl_millet", "groundnut", "sesame", "castor", "sunflower", "soybean", "cowpea", "bengal_gram", "redgram", "turmeric", "chilli",
                "tomato_plant", "brinjal_plant", "onion_bulbs", "okra", "sugarcane_field", "coconut_palms", "banana_plantation", "cotton_boll", "maize_field"}


_TAMIL_TOPICS = {"பூச்சி": "pest", "புழு": "worm", "நோய்": "disease", "உரம்": "fertilizer", "விதை": "seed", "களை": "weed", "அறுவடை": "harvest", "நீர்ப்பாசனம்": "irrigation",
                 "சொட்டு": "drip", "தெளிப்பு": "sprinkler", "மண்": "soil", "மண்புழு": "vermicompost", "மக்கு": "compost", "வாடல்": "wilt", "அசுவினி": "aphid", "வெள்ளை ஈ": "whitefly",
                 "படைப்புழு": "armyworm", "தண்டுத்துளைப்பான்": "borer", "குருத்து": "borer", "இலைப்புள்ளி": "spot", "துரு": "rust", "பொட்டாஷ்": "potassium", "தழைச்சத்து": "nitrogen",
                 "padaiyal": "armyworm", "padai puzhu": "armyworm", "thandu thulaippan": "borer", "pooch": "pest", "noi ": "disease", "vaadal": "wilt", "vadal": "wilt", "uram": "fertilizer", "vithai": "seed", "kalai": "weed"}


def _tokens(text: str) -> set[str]:
    t = (text or "").lower()
    out = {x for x in re.findall(r"[a-z]{3,}", t) if x not in _STOP}
    out |= {en for ta, en in _TAMIL_TOPICS.items() if ta in t}                 # the farmer's Tamil topic word counts the same as its English word
    return out


def _library() -> dict:
    try:
        return json.loads((config.DATA_DIR / "images" / "library.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def library_photos(query: str, crop: str | None = None, limit: int = 2) -> list[dict]:
    """Photos from the local library that fit the question. A question about a pest or deficiency only gets pest or deficiency photos (never a crop-field picture), a plain crop question
    only gets that crop; at least one distinctive word must match. Returns [] when nothing fits."""
    q = _tokens(query) | _tokens(crop or "")
    if not q:
        return []
    problem = bool(_PROBLEM.search(query or "")) or bool(_tokens(query) & {"pest", "worm", "disease", "borer", "wilt", "armyworm", "aphid", "whitefly", "spot", "rust", "mildew", "potassium", "nitrogen"})
    scored: dict[str, list] = {}
    for it in _library().values():
        if not it.get("reviewed") or not (config.DATA_DIR / "images" / it["file"]).exists():
            continue
        topic = it["topic"]
        if problem and topic not in _PROBLEM_TOPICS:
            continue
        if not problem and topic in _PROBLEM_TOPICS and not re.search(r"look|photo|picture|image|show", query or "", re.I):
            continue
        hit = q & _tokens(it["words"])
        topic_q = q - _CROPS - _WEAK
        if not (hit - _WEAK) or (topic_q and not (hit & topic_q)):         # a question about a pest or practice needs a photo of that, not just of the crop
            continue
        scored.setdefault(topic, []).append((len(hit), it))
    if not scored:
        return []
    best = max(scored.items(), key=lambda kv: max(s for s, _ in kv[1]))
    out = []
    for _s, it in sorted(best[1], key=lambda x: -x[0])[:limit]:
        out.append({"id": it["id"], "url": f"/images/{it['file']}", "label": it["label"], "credit": f"{it['author']}, {it['license']} (Wikimedia Commons)", "page": it.get("page")})
    return out


# ── real videos from TNAU TV (data/videos.json, built and verified by scripts/build_video_catalog.py) ────────────────────────────────────────
def _videos() -> list[dict]:
    try:
        return json.loads((config.DATA_DIR / "videos.json").read_text(encoding="utf-8")).get("videos", [])
    except Exception:  # noqa: BLE001
        return []


def tnau_videos(query: str, crop: str | None = None, limit: int = 2) -> list[dict]:
    """Videos from the official TNAU TV channel that fit the question. If the question names a topic besides the crop (pest, disease, practice), a title must contain that topic word;
    a video about a different crop is never shown. A question that only names a crop may match that crop's videos."""
    qt = _tokens(query)
    ct = _tokens(crop or "") | (qt & _CROPS)
    topic = qt - _CROPS - _GENERIC - ct
    scored = []
    for v in _videos():
        tt = _tokens(v["title"])
        others = (tt & _CROPS) - ct
        if others and not (tt & ct):
            continue                                        # about another crop
        if topic:
            if len(topic & tt) < min(2, len(topic)):
                continue
            score = 2 * len(topic & tt) + len(ct & tt)
        else:
            if not (ct & tt):
                continue
            score = len(ct & tt)
        scored.append((score, v))
    scored.sort(key=lambda x: -x[0])
    return [{"id": v["id"], "title": v["title"], "url": v["url"], "channel": v.get("channel") or "TNAU TV"} for _s, v in scored[:limit]]


# ── outside search, only when the local library has nothing (cached on disk; strict licence and title checks) ───────────────────────────────
import hashlib
import os

_EXT_FILE = "library_ext.json"


def external_photo(query: str, crop: str | None = None) -> dict | None:
    """One photo from Wikimedia Commons for a question the local library cannot illustrate. Kept only if its licence allows reuse with attribution (CC0, public domain,
    CC BY, CC BY-SA), its title contains the question's distinctive words, and it is a real photograph of useful size. It is downloaded once and cached; the caption says it was
    matched by its title and has not been checked by Cropsy. Returns None on any failure or doubt. Turn off with CROPSY_EXTERNAL_IMAGES=0."""
    if os.getenv("CROPSY_EXTERNAL_IMAGES", "1") != "1":
        return None
    topic = _tokens(query) - _CROPS - _WEAK - _GENERIC
    need = (topic or _tokens(query))
    if not need or len(" ".join(need)) < 4:
        return None
    key = hashlib.sha1(f"{sorted(need)}|{crop}".encode()).hexdigest()[:12]
    idx_path = config.DATA_DIR / "images" / _EXT_FILE
    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
    except Exception:  # noqa: BLE001
        idx = {}
    if key in idx:
        it = idx[key]
        return it if it and (config.DATA_DIR / "images" / it["file"]).exists() else None
    import requests
    ses = requests.Session()
    ses.headers["User-Agent"] = "CropsyDemo/1.0 (educational farm advisory)"
    q = " ".join(sorted(need, key=len, reverse=True)[:3]) + (f" {crop}" if crop else "")
    item = None
    try:
        r = ses.get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "generator": "search", "gsrsearch": q + " filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 6,
                    "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 800, "format": "json"}, timeout=4).json()
        for p in sorted((r.get("query", {}).get("pages", {}) or {}).values(), key=lambda p: p.get("index", 99)):
            ii = (p.get("imageinfo") or [{}])[0]
            m = ii.get("extmetadata", {})
            lic = (m.get("LicenseShortName", {}).get("value") or "").strip()
            if not re.match(r"^(CC0|Public domain|CC BY(-SA)? \d(\.\d)?( [A-Za-z]{2})?)$", lic, re.I) or ii.get("mime") != "image/jpeg" or ii.get("width", 0) < 500:
                continue
            title_t = _tokens(re.sub(r"[_.]", " ", p["title"]))
            if not (need & title_t) or (len(need) >= 2 and len(need & title_t) < min(2, len(need))):
                continue                                    # the title must carry the question's own distinctive words
            b = ses.get(ii["thumburl"], timeout=6).content
            if len(b) < 8000:
                continue
            fid = f"ext_{key}.jpg"
            (config.DATA_DIR / "images" / "library" / fid).write_bytes(b)
            item = {"file": f"library/{fid}", "label": re.sub(r"^File:|\.\w+$", "", p["title"]).replace("_", " "), "credit": f"{re.sub('<[^>]+>', '', m.get('Artist', {}).get('value', 'unknown')).strip()[:60]}, {lic} (Wikimedia Commons)",
                    "page": ii.get("descriptionurl"), "auto": True}
            break
    except Exception as e:  # noqa: BLE001
        log.info("external image search skipped: %s", e)
        return None
    idx[key] = item
    try:
        idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return item
