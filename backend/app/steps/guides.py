"""
guides.py: "how to make it / how to apply it" cards shown under fertilizer questions: a photo, plain steps, and where to watch a tutorial.

Fixed, reviewed content (no language model). Home-made recipes follow the TNAU organic-farming method; mineral-fertilizer handling follows
general extension practice. No dose is invented here: the amount for the crop comes from the answer's own TNAU source.
Videos are search links, not embedded clips: the clips could not be checked from here, so each link says it is a search.
"""
from __future__ import annotations

import json
import re
import time
from urllib.parse import quote_plus

from app import config
from app.schemas import PipelineState
from app.steps import guides_dynamic as _gd
from app.steps import guides_knowledge as _gk

TNAU_TRAINING = {"title": "TNAU organic farming training notes (Panchagavya, Jeevamrutham)", "url": "https://agritech.tnau.ac.in/org_farm/pdf/Training-eng%20(1).pdf"}
TNAU_PORTAL = {"title": "TNAU Agritech Portal: organic farming", "url": "https://agritech.tnau.ac.in/"}
EXTENSION = {"title": "Fertilizer application guidance (extension notes)", "url": "https://www.bighaat.com/hi/kisan-vedika/blogs/urea-fertilizer-uses-dosage-application"}


CAPTIONS = {
    "cans": "Clay pots used to ferment Jeevamrut-type cow-urine and dung preparations", "dungheap": "Cow dung heap, the base of panchagavya, jeevamrutham and compost",
    "vermicompost": "Earthworms working in compost", "vermicast": "Finished, dark, crumbly vermicompost in a bed", "wormbed": "A shaded worm bed with straw bedding",
    "fym": "Farmyard manure heap (cover it from rain)", "organic": "Dry organic matter breaking down", "urea": "Urea granules (white, round prills)",
    "dap": "DAP granules (dark, hard granules)", "topdress": "Spreading fertilizer by hand (older photo)",
    "fence_solar": "Solar-powered electric fence: panel, energizer and posts", "fence_elephant": "Electric fence wires on a forest edge in Sri Lanka",
    "fence_energiser": "A fence energizer: the box that sends the short, harmless pulses", "fence_barbed": "Barbed-wire fence on posts",
    "em_flood": "Standing water in a flooded field", "em_drain": "A drainage channel at the field edge: keep it open", "em_drought": "Cracked, dry soil: roots are already stressed",
    "em_hail": "Hail damage on stems and leaves", "em_storm": "A banana plant knocked down by wind", "em_fire": "Fire in a field at night", "em_locust": "Locust swarm in the air and on the ground",
    "w_rain": "Paddy fields in the rain", "em_sign": "A pesticide-spraying warning sign: keep away until the waiting time has passed", "em_aid": "A first-aid box: keep one at home and in the field hut",
    "fence_chain": "Chain-link fence around a field", "scarecrow": "Scarecrow in a crop field (birds only)",
}


GUIDES_FROM_KNOWLEDGE = True


def _credit(key: str) -> dict | None:
    try:
        c = json.loads((config.DATA_DIR / "images" / "fertilizer" / "credits.json").read_text(encoding="utf-8"))[key]
    except Exception:  # noqa: BLE001
        return None
    return {"url": f"/images/{c['file']}", "credit": f"{c['author']}, {c['license']}", "page": c["page"]}


def _videos(*terms: str) -> list[dict]:
    return [{"label": t, "url": "https://www.youtube.com/results?search_query=" + quote_plus(t)} for t in terms]


GUIDES = {
    "panchagavya": {
        "title": "Panchagavya (home-made, cow-based growth tonic)", "kind": "natural", "photos": ["cans", "dungheap"],
        "steps": [
            "Mix 7 kg fresh cow dung with 1 litre cow ghee, stir well and keep for 3 days (stir daily).",
            "Add 10 litres cow urine and 10 litres water; keep in shade, stir twice a day for 15 days.",
            "Then add 3 litres cow milk, 2 litres curd, 3 litres tender coconut water, 3 kg jaggery and 12 ripe bananas.",
            "Stir morning and evening; the stock solution is ready after about 30 days.",
            "Use the strength and timing your TNAU extension officer recommends for your crop; do not spray on a hot afternoon.",
        ],
        "source": TNAU_TRAINING,
        "videos": _videos("panchagavya preparation tamil TNAU", "panchagavya how to make farmers"),
    },
    "jeevamrutham": {
        "title": "Jeevamrutham (home-made microbial culture for soil)", "kind": "natural", "photos": ["cans"],
        "steps": [
            "Ingredients: fresh cow dung, cow urine, jaggery, pulse (legume) flour and a handful of healthy soil from the field bund.",
            "Mix in a barrel with water, keep in shade, stir morning and evening for a few days until it ferments.",
            "Apply to the soil, for example with irrigation water, as your TNAU or natural-farming trainer advises for your crop.",
        ],
        "source": TNAU_TRAINING,
        "videos": _videos("jeevamrutham preparation tamil", "jeevamrutham natural farming how to make"),
    },
    "vermicompost": {
        "title": "Vermicompost (earthworm compost) at home", "kind": "natural", "photos": ["vermicompost", "vermicast"],
        "steps": [
            "Make a shaded bed or bin with drainage; lay dry leaves and straw as bedding.",
            "Add partly decomposed cow dung and farm waste (no oil, salt, meat or citrus), then the composting earthworms.",
            "Keep it damp like a squeezed sponge, never waterlogged, and always shaded.",
            "When the material turns dark, crumbly and earthy, move the worms aside and sieve it: that is vermicompost.",
        ],
        "source": TNAU_PORTAL,
        "videos": _videos("vermicompost preparation tamil farmers", "vermicompost bed how to make India"),
    },
    "fym": {
        "title": "Farmyard manure and compost", "kind": "natural", "photos": ["fym", "organic"],
        "steps": [
            "Heap cow dung, straw and crop residue in a shaded pit or covered heap so rain does not wash the nutrients out.",
            "Turn it now and then and keep it damp; use it only when it is dark, crumbly and no longer smells.",
            "Spread it evenly and mix it into the soil before planting.",
        ],
        "source": TNAU_PORTAL,
        "videos": _videos("farmyard manure compost making tamil", "compost pit making farmers India"),
    },
    "urea": {
        "title": "Urea: how to put it on the field", "kind": "mineral", "photos": ["urea", "topdress"],
        "steps": [
            "Use the amount in the TNAU answer for your crop and stage, split into the rounds it lists; more at once is wasted and can burn plants.",
            "Spread evenly by hand or place it a short distance from the plant and cover it with soil; do not leave it on the surface in hot sun or just before heavy rain.",
            "Weed first, so the weeds do not take the nitrogen.",
            "Wear gloves, keep it away from children and do not store it near seed.",
        ],
        "source": EXTENSION,
        "videos": _videos("urea top dressing method paddy tamil", "how to apply urea fertilizer correctly"),
    },
    "dap": {
        "title": "DAP: when and how to apply", "kind": "mineral", "photos": ["dap", "topdress"],
        "steps": [
            "DAP gives phosphorus early, so it goes in at planting or as basal dose, mixed into the soil near the root zone.",
            "Use the amount in the TNAU answer for your crop; get a soil test first if you can.",
            "Do not put it touching the seed. Store dry.",
        ],
        "source": EXTENSION,
        "videos": _videos("DAP basal application method farmers tamil", "how to apply DAP fertilizer"),
    },
}

GUIDES["fence_electric"] = {
    "title": "Solar electric fence against wild boar, elephant and monkey", "kind": "protection", "photos": ["fence_solar", "fence_energiser", "fence_elephant"],
    "steps": [
        "Use a solar fence with a certified energizer that sends short, low-energy pulses. Never connect fence wires to mains power: that kills people and animals and is illegal.",
        "Post the fence on the side the animals come from (forest edge, stream line); a few well-spaced wire strands at the animal's chest height are what turns boar and elephants back.",
        "Keep grass and branches off the wires, because touching vegetation drains the pulse. Check the earthing and the battery on a fixed day each week.",
        "Put warning boards on every side and keep children and cattle away from the wires.",
        "Ask the Forest Department and your KVK for the approved design and for any subsidy; a village-level shared fence costs much less per farmer than one fence per plot.",
    ],
    "notes": ["Setup cost is high and the fence needs regular upkeep; it is worth it mainly for parcels at the forest edge (foothill zone).",
              "Monkeys climb and jump over it, so it works best against boar and elephant."],
    "warning": "Only a certified solar energizer. Do not use mains electricity or home-made live wires.",
    "source": {"title": "KFRI: crop damage by wild animals and mitigation (Kerala Forest Research Institute)", "url": "https://docs.kfri.res.in/xxxxKFRI-RR/KFRI-RR491.pdf"},
    "videos": _videos("solar electric fence for farm wild boar elephant India", "solar fence installation farmers tamil"),
}
GUIDES["fence_physical"] = {
    "title": "Other ways to protect the land: fences, trench, hedge, watch and noise", "kind": "protection", "photos": ["fence_barbed", "fence_chain", "scarecrow"],
    "steps": [
        "Barbed wire or chain-link on posts keeps out stray cattle and deer; it is not enough alone against elephants or determined boar.",
        "Where elephants come, villages and the Forest Department dig a trench or build a stone wall along the forest edge; this is a shared work, not a single-plot job.",
        "A thorny live hedge (such as prickly pear or agave) on the field bund slows boar and cattle and costs little, but takes years to grow.",
        "Smelly or hot barriers (chilli-tobacco rope, chilli-ash) and noise (drums, torches, a night watch from a raised hut) turn animals back for a short time; change them often so animals do not get used to them.",
        "Guard the crop most closely in the weeks of grain filling or fruit ripening, when raids peak.",
        "Report every raid to the Forest Department so the loss can be recorded for compensation.",
    ],
    "notes": ["No barrier is raid-proof; the best results come from combining two or three methods, shared by neighbouring farmers."],
    "source": {"title": "ICAR: vertebrate pest management in crops", "url": "https://epubs.icar.org.in/index.php/AAZ/article/view/168758/62578"},
    "videos": _videos("farm fencing methods wild animals India tamil", "elephant proof trench farm protection"),
}

CONTACTS = [
    {"name": "Emergency (police, fire, medical)", "number": "112"},
    {"name": "Ambulance", "number": "108"},
    {"name": "Kisan Call Centre (free farm advice)", "number": "1800-180-1551"},
    {"name": "Tamil Nadu disaster helpline", "number": "1070"},
    {"name": "District disaster control room", "number": "1077"},
    {"name": "Crop insurance (PMFBY) helpline", "number": "14447"},
]
_INSURE = "If the crop is insured, report the loss on the PMFBY helpline or to your bank or insurer within 72 hours, and keep photos with the date."
_EM_SRC = {"title": "TNAU Agritech Portal and NDMA farm-disaster guidance", "url": "https://agritech.tnau.ac.in/"}


def _em(title, photos, steps, notes=None, warning=None, videos=()):
    return {"title": title, "kind": "emergency", "photos": photos, "steps": steps, "notes": notes or [], "warning": warning, "source": _EM_SRC,
            "videos": _videos(*videos) if videos else [], "contacts": CONTACTS}


GUIDES["em_flood"] = _em("EMERGENCY: flood or standing water in the field", ["em_flood", "em_drain"], [
    "Stay safe first: do not walk into flowing water or touch electric wires or pumps.",
    "As soon as water falls, open drainage channels and bund cuts so it can leave; every day under water hurts roots.",
    "Rice can stand a few days under water; most other crops (maize, banana, turmeric, groundnut, chilli) cannot, so drain these first.",
    "After the water goes, do not walk on or work the wet soil; wait for it to firm up. Remove silt and dead leaves from plants.",
    "Watch for disease in the days after (leaf spots, rot, wilt): see the photo advice in Cropsy for your crop.",
    _INSURE,
], notes=["Ask your KVK before applying any fertilizer or spray after a flood: roots are damaged and may not take it up."], videos=("flooded field crop recovery after flood farmers",))
GUIDES["em_drought"] = _em("EMERGENCY: drought, heat wave or water shortage", ["em_drought"], [
    "Give the little water you have to the crop stage that needs it most: flowering and grain or fruit filling, then young plants.",
    "Irrigate early morning or evening, and in small, frequent amounts at the root rather than flooding.",
    "Cover the soil with straw, dry leaves or crop residue (mulch) to cut evaporation; remove weeds that take the water.",
    "Do not apply fertilizer to dry soil; wait for moisture.",
    "If water will not last, ask your KVK which part of the field to save, and about relief and drought-tolerant options.",
    _INSURE,
], notes=["Cracks in the soil mean the roots are already stressed; water slowly so it soaks in."], videos=("drought management crops mulching farmers tamil",))
GUIDES["em_storm"] = _em("EMERGENCY: cyclone, strong wind or hailstorm", ["em_storm", "em_hail"], [
    "Before the storm: harvest what is ready, tie up banana and tall crops, clear drains, and move seed, fertilizer and pumps to a dry, high place.",
    "During the storm: stay indoors, away from trees, poles and wires.",
    "After the storm: photograph all damage with the date before you clean up (needed for insurance and relief).",
    "Drain standing water, remove broken leaves and stems, and prop up leaning plants where they are still alive.",
    "Cut and clear fallen coconut fronds and broken banana plants so rot and pests do not build up.",
    _INSURE,
], notes=["Do not spray or fertilize straight after a hailstorm; torn leaves take chemicals up too fast. Ask your KVK when to restart."], videos=("cyclone damaged banana coconut recovery farmers",))
GUIDES["em_fire"] = _em("EMERGENCY: fire in or near the field", ["em_fire"], [
    "Your life first: move people and cattle away and call 112 or the fire service.",
    "Do not try to fight a large fire alone, and do not drive through smoke.",
    "Cut a firebreak (a cleared strip) between the fire and the standing crop and dry residue, if you can do it safely.",
    "After the fire: photograph the damage with the date, tell the village officer and your insurer, and keep burnt cane or crop for the mill or buyer record.",
    "Do not burn crop residue; it spreads fire and kills the soil life.",
], warning="Do not go into the fire. Call 112.", videos=("farm fire safety firebreak sugarcane",))
GUIDES["em_pest"] = _em("EMERGENCY: sudden pest outbreak (locusts, armyworm, swarm of insects)", ["em_locust"], [
    "Tell your village officer, KVK or the Kisan Call Centre the same day, with photos; outbreaks are managed by the whole area, not field by field.",
    "Walk the field early and note where it started and how far it has spread.",
    "Do not spray any pesticide on your own guess. Ask the KVK which product is registered for the pest and your crop and the safe dose.",
    "If you spray: read the label, wear gloves, mask and full clothing, spray with the wind behind you, and keep children and animals away.",
    "Remove and destroy badly hit plants if the KVK advises it.",
], notes=["For fall armyworm in maize, upload a photo in Cropsy: it shows leaf and whorl damage and the TNAU advice for your stage."], warning="Never mix pesticides or reuse empty containers.", videos=("fall armyworm management maize tamil TNAU",))
GUIDES["em_poison"] = _em("EMERGENCY: pesticide poisoning", ["em_sign"], [
    "Move the person away from the spray and into fresh air at once.",
    "Take off contaminated clothes and wash skin and hair well with soap and water; rinse eyes with clean water for several minutes if splashed.",
    "Do NOT make them vomit and do not give milk, oil or anything to drink unless a doctor tells you to.",
    "Call 108 or take them to the nearest hospital immediately, and take the pesticide container or label with you.",
    "Keep children away; never reuse the empty container.",
], warning="Call 108 now. This is a medical emergency.", videos=())
GUIDES["em_help"] = _em("EMERGENCY: who to call and what to do first", ["em_aid"], [
    "If anyone is hurt or in danger, call 112 (emergency) or 108 (ambulance) first. The crop can wait.",
    "Tell me what happened (flood, drought, cyclone or hail, fire, pests, pesticide poisoning, wild animals) and I will give the steps for it.",
    "Photograph the damage with the date before you clean up; you need it for insurance and relief.",
    "For farm advice call the Kisan Call Centre (free); for crop insurance call the PMFBY helpline within 72 hours of the loss.",
], videos=())
GUIDES["em_animal"] = _em("EMERGENCY: wild animals in the field right now", ["fence_solar", "scarecrow"], [
    "Do not go close to elephants or boar at night; keep people and cattle indoors and away.",
    "Call the Forest Department range office or the village emergency contact; for people in danger call 112.",
    "Make noise and light from a safe distance (torches, drums) to turn them back; do not chase or corner them.",
    "After the raid, photograph the damage and tracks, and report it so loss can be recorded for compensation.",
    "Do not use home-made live wires or mains electricity to keep animals out: people and animals are killed this way.",
], warning="Keep a safe distance from elephants and boar. Never use live wires.", videos=())

_TRIGGERS = [
    ("panchagavya", r"panch?a\s?gavya|panchakavya|பஞ்சகவ்ய"),
    ("jeevamrutham", r"jeeva\s?m?r[ui]th?am|jeevamrit|ஜீவாமிர்த"),
    ("vermicompost", r"vermi\s?-?compost|earth\s?worm|worm\s?compost|மண்புழு"),
    ("fym", r"farm\s?yard|\bfym\b|cow\s?dung|compost|manure|கம்போஸ்ட்|எரு"),
    ("urea", r"\burea\b|யூரியா"),
    ("dap", r"\bdap\b|diammonium|டிஏபி"),
    ("em_poison", r"poison|vomit|swallow\w*\s+(pesticide|spray)|pesticide\s+(on|in)\s+(skin|eye)|விஷம்"),
    ("em_fire", r"\bfire\b|burn(ing|t)\s+(field|crop|cane)|தீ\s?விபத்து|தீப்பிடி"),
    ("em_storm", r"cyclone|hail\s?storm|\bhail\b|storm|strong wind|புயல்|ஆலங்கட்டி"),
    ("em_flood", r"flood|waterlog|standing water|inundat|heavy rain damage|வெள்ளம்"),
    ("em_drought", r"drought|heat\s?wave|water shortage|no water|வறட்சி"),
    ("em_pest", r"locust|swarm|armyworm outbreak|pest outbreak|sudden pest|வெட்டுக்கிளி"),
    ("em_animal", r"(elephant|boar|animals?|monkeys?|yaanai|யானை|பன்றி).{0,30}(now|entered|inside|in my (field|farm|land)|came|coming)|emergency.{0,20}(animal|wild|elephant|boar)"),
    ("em_help", r"emergency|urgent|urgently|help me|sos|அவசர"),
    ("fence_electric", r"electric\s?fenc|solar\s?fenc|min\s?vel|மின்\s?வேலி|fence energi"),
    ("fence_physical", r"\bfenc|வேலி|trench|\bbarrier|protect\w*\s+(my\s+|the\s+)?(land|field|farm|crop|parcel)s?\s+(from|against)\s+(animals?|wild\w*|elephants?|boar|pigs?|monkeys?|deer|cattle|birds?|thie\w+|theft)|land\s+protection|scarecrow|watch\s?tower|machan"),
]
_WILD = re.compile(r"(wildlife|wild\s?animal|boar|\bpig\b|elephant|monkey|macaque|peafowl|peacock|deer|porcupine|animals?\b|யானை|பன்றி|குரங்கு|காட்டு)", re.IGNORECASE)
GUIDE_ONLY = {"em_flood", "em_drought", "em_storm", "em_fire", "em_pest", "em_poison", "em_animal", "em_help", "panchagavya", "jeevamrutham", "vermicompost", "fym", "fence_electric", "fence_physical"}
GUIDES.update(_gk.KNOWLEDGE)
CAPTIONS.update(_gk.CAPTIONS)
_TRIGGERS.extend(_gk.TRIGGERS)
GUIDE_ONLY |= {k for k in _gk.KNOWLEDGE if k not in _gk.CARD_ONLY}
_GENERIC_NATURAL = re.compile(r"(organic|natural|home\s?-?made|bio\s?fertili[sz]er|iyarkai|இயற்கை)", re.IGNORECASE)
_HOW = re.compile(r"(fertili[sz]er|urea|dap|manure|compost|tutorial|video|how to (make|apply|prepare)|eppadi|எப்படி|dose|dosage|evlo|எவ்வளவு)", re.IGNORECASE)


_CACHE: dict = {}


def guides_for(state: PipelineState, limit: int = 3) -> list[dict]:
    if state.doc_text:
        return []
    q = f"{state.query} {state.normalized_query or ''}".lower()
    keys = [k for k, rx in _TRIGGERS if re.search(rx, q, re.IGNORECASE)]
    if not keys and _GENERIC_NATURAL.search(q) and _HOW.search(q):
        keys = ["panchagavya", "vermicompost"]
    if _WILD.search(q):                                 # a wildlife question also gets the protection options
        keys += [k for k in ("fence_electric", "fence_physical") if k not in keys]
    if any(k.startswith("em_") and k != "em_help" for k in keys):
        keys = [k for k in keys if k != "em_help"]
    cards = _build(keys[:limit]) + _finish(_gd.dynamic_extra(state))
    return _drop_tn_only(cards, state)


# fixed cards written for Tamil Nadu (kuruvai/samba seasons, the village crop calendar): not shown under an answer for a farmer in another state or country
_TN_ONLY_CARDS = {"season", "calendar"}


def _drop_tn_only(cards: list[dict], state: PipelineState) -> list[dict]:
    r = state.region or {}
    if (r.get("state") and r["state"] != "Tamil Nadu") or (r.get("country") and r["country"] != "India"):
        return [c for c in cards if c.get("id") not in _TN_ONLY_CARDS and c.get("kind") != "calendar"]
    return cards


def _build(keys: list[str]) -> list[dict]:
    out = []
    for k in keys:
        g = GUIDES[k]
        photos = []
        for key in g["photos"]:
            c = _credit(key)
            if c:
                c["caption"] = CAPTIONS.get(key, "")
                photos.append(c)
        out.append({"id": k, "title": g["title"], "kind": g["kind"], "steps": g["steps"], "source": g["source"], "videos": g["videos"],
                    "photos": photos, "notes": g.get("notes", []), "warning": g.get("warning"), "contacts": g.get("contacts", []), "extra_sources": g.get("extra_sources", [])})
    return out


_EXPLICIT = re.compile(r"(how|make|prepar|build|install|set\s?up|protect|prevent|keep\s+out|stop|tutorial|video|detail|what|tell|explain|eppadi|எப்படி|செய்|பாது)", re.IGNORECASE)


def _guide_only_core(state: PipelineState) -> list[dict]:
    """A how-to-make / how-to-protect / emergency question the guides answer completely: answered from the guide, no language model."""
    q = f"{state.query} {state.normalized_query or ''}".lower()
    found = [k for k, rx in _TRIGGERS if k in GUIDE_ONLY and re.search(rx, q, re.IGNORECASE)]
    em = [k for k in found if k.startswith("em_") and k != "em_help"]
    if em:                                                  # an emergency never waits for "how": show the matching steps first
        return _build(em[:2])
    if "em_help" in found:
        return _build(["em_help"])
    knowledge = [k for k in found if k in _gk.KNOWLEDGE and k not in _gk.CARD_ONLY]
    if knowledge:                                           # a specific topic word (scheme, soil sample, mandi...): answer from the card
        return _build(knowledge[:2])
    if not _EXPLICIT.search(q):
        return []
    found = [k for k in found if not k.startswith("em_")]
    if not found:
        if not (_GENERIC_NATURAL.search(q) and _HOW.search(q)):
            return []
        found = ["panchagavya", "vermicompost"]
    if any(k.startswith("fence") for k in found):
        return guides_for(state)
    return [g for g in guides_for(state) if g["id"] in found] or guides_for(state)


def is_planner(state: PipelineState) -> bool:  # also: combined-alert questions
    if _gd._PRIO.search(f"{state.query} {state.normalized_query or ''}".lower()):
        return True
    return bool(_gd._PLAN.search(f"{state.query} {state.normalized_query or ''}".lower())) and bool(state.parcel_context)


def is_emergency(state: PipelineState) -> bool:
    q = f"{state.query} {state.normalized_query or ''}".lower()
    return any(k.startswith("em_") and re.search(rx, q, re.IGNORECASE) for k, rx in _TRIGGERS)


def _finish(cards: list[dict]) -> list[dict]:
    """Dynamic cards name photos by key or path: turn them into photo entries with credits."""
    for c in cards:
        out = []
        for ph in c.get("photos") or []:
            if isinstance(ph, str):
                cr = _credit(ph)
                if cr:
                    cr["caption"] = CAPTIONS.get(ph, "")
                    out.append(cr)
            else:
                out.append(ph)
        if c.get("raw_photo"):
            out.append({"url": c["raw_photo"], "credit": "sample photo (dummy), public dataset", "page": "", "caption": "Sample photo of this crop (not your field)"})
        c["photos"] = out
        c.pop("raw_photo", None)
    return cards


def guide_only(state: PipelineState) -> list[dict]:
    """Fixed guides first, then the situation cards (calendar, gallery, weather), then, if the question is not understood, a clarifying card."""
    if state.doc_text:                                  # an attached document is explained from its own text, not matched to a guide card
        return []
    key = (state.query, state.parcel_id, state.normalized_query)
    hit = _CACHE.get("only")
    if hit and hit[0] == key and time.time() - hit[1] < 30:
        return hit[2]
    q = f"{state.query} {state.normalized_query or ''}".lower()
    if not is_emergency(state):
        from app import corrections
        fix = corrections.find(state.query, state.parcel_id)
        if fix:                                            # an agriculture officer has reviewed this question: show their answer
            when = (fix.get("time") or "")[:10]
            card = {"id": "reviewed", "title": f"Reviewed by {fix['officer']}, agriculture officer" + (f" ({when})" if when else ""), "kind": "reviewed", "message": fix["corrected_answer"],
                    "steps": [], "photos": [], "notes": ([fix["note"]] if fix.get("note") else []) + ["This answer was written or corrected by an officer for this question. Cropsy shows it instead of an automatic answer."],
                    "warning": None, "videos": [], "contacts": [], "extra_sources": [], "asks": [], "source": {"title": "Officer review", "url": "https://agritech.tnau.ac.in/"}, "officer": fix["officer"]}
            r = [card]
            _CACHE["only"] = (key, time.time(), r)
            return r
    if _gd.OFFICES_RX.search(q) and not is_emergency(state):
        c = _gd.offices_card(state)
        r = _finish([c]) if c else []
        _CACHE["only"] = (key, time.time(), r)
        return r
    r = _guide_only_core(state)
    if not r:
        d = _gd.dynamic_only(state)
        r = _finish(d) if d else []
    if not r and not state.image_bytes:
        c = _gd.clarify_card(state)
        r = _finish([c]) if c else []
    _CACHE["only"] = (key, time.time(), r)
    return r


def guide_text(gs: list[dict]) -> str:
    parts = []
    for g in gs:
        if g.get("message"):
            parts.append(g["message"])
            continue
        body = chr(10).join(f"{i}. {t}" for i, t in enumerate(g["steps"], 1))
        caution = (chr(10) + "Caution: " + g["warning"]) if g.get("warning") else ""
        calls = (chr(10) + "Call: " + "; ".join(f"{c['name']} {c['number']}" for c in g["contacts"])) if g.get("contacts") else ""
        parts.append(g["title"] + ":" + chr(10) + body + caution + calls)
    return (chr(10) * 2).join(parts)
