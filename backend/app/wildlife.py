"""
wildlife.py: crop-raiding animals and what deters them, for the foothill village of Then Malai (Tenkasi, Western Ghats).

Everything here is a rule-based indication, never a guarantee. It combines three things:
  1. which animals live along the Western Ghats foothills (published studies and press reports, below),
  2. which crops those animals are reported to raid, or to avoid, in the same region,
  3. the parcel's zone (foothill / terrace / valley), because forest-edge parcels are raided more.
The parcel record's own "intrusion" fields are dummy data and are shown as such.
No lethal control, poison or illegal electric fence is ever suggested: wildlife is protected, and damage should be reported to the
Forest Department / local officer (compensation schemes exist).
"""
from __future__ import annotations

import json

from app import config

SOURCES = {
    "boar": {"title": "Wild boar: a chronic, under-recognised driver of agricultural loss (Kisan Swaraj)", "url": "https://coexistence.kisanswaraj.in/?p=48"},
    "boar_tn": {"title": "Tamil Nadu: wild boar damage to paddy, sugarcane, groundnut and banana (The News Minute)",
                "url": "https://www.thenewsminute.com/tamil-nadu/tamil-nadu-govt-start-culling-wild-boars-responsible-crop-loss-55156"},
    "boar_wg": {"title": "Western Ghats (Kerala) boar damage study: cassava, taro, yams and ginger rhizomes dug up", "url": "https://caves.res.in/journal/articles/Amb_Sci_10(2)_Aa01.pdf"},
    "elephant_cbe": {"title": "Human-elephant conflict, Coimbatore Forest Division, Tamil Nadu: banana, sorghum, areca and coconut most raided (Frontiers in Conservation Science, 2023)",
                     "url": "https://frontiersin.org/journals/conservation-science/articles/10.3389/fcosc.2023.1142325/full"},
    "elephant_buffer": {"title": "Unpalatable crop buffers (chilli, tea, ginger, mustard, sunflower, moringa, lemon) against elephants (Frontiers in Conservation Science, 2022)",
                        "url": "https://www.frontiersin.org/articles/10.3389/fcosc.2022.863180/pdf"},
    "elephant_indigenous": {"title": "Indigenous knowledge to deter elephants from crop lands (turmeric, coriander, mint, basil, lemongrass reported less attractive)",
                            "url": "https://journals.sjp.ac.lk/index.php/jich/article/view/7930"},
    "monkey": {"title": "Monkey-farmer conflict and types of damage (Kisan Swaraj)", "url": "https://coexistence.kisanswaraj.in/?p=77"},
    "kfri": {"title": "KFRI research report on crop damage by wild animals and mitigation (Kerala Forest Research Institute)", "url": "https://docs.kfri.res.in/xxxxKFRI-RR/KFRI-RR491.pdf"},
    "icar": {"title": "ICAR: vertebrate pest management in crops", "url": "https://epubs.icar.org.in/index.php/AAZ/article/view/168758/62578"},
}

# animal -> (where, crops reported raided, most vulnerable time, deterrents, source keys)
ANIMALS: dict[str, dict] = {
    "Wild boar": {
        "where": "forest edge and foothills; moves onto terraces and valley fields at night",
        "raids": ["Maize", "Groundnut", "Sugarcane", "Rice", "Banana", "Turmeric", "Coconut"],
        "evidence": "strong",
        "note": "Roots up tubers and rhizomes (yams, ginger), newly sown groundnut and maize; paddy, sugarcane and banana are also reported damaged in Tamil Nadu.",
        "when": "newly sown fields, pod and rhizome stages, and ripening grain at night",
        "deterrents": ["A trench or sturdy fence on the forest-side boundary", "Night watch with lights and noise (rotate the position)",
                       "Smell or taste repellents on boundary rows",
                       "Report damage to the Forest Department; do not use poison or illegal live wires"],
        "sources": ["boar", "boar_tn", "boar_wg", "icar"],
    },
    "Elephant": {
        "where": "Western Ghats forest edge with elephant movement; possible only for parcels close to the forest",
        "raids": ["Banana", "Sugarcane", "Rice", "Coconut", "Maize"],
        "evidence": "strong",
        "note": "In a Tamil Nadu study (Coimbatore) the most raided crops were banana, sorghum, areca nut and young coconut palms (under about 20 years).",
        "when": "banana and sugarcane near maturity, and at night during the post-monsoon harvest",
        "deterrents": ["Report sightings early to the Forest Department rapid-response team", "Chilli, ginger, mustard or tea buffer strips on the forest side",
                       "Community early-warning and watch", "Keep ripe produce out of the field and out of storehouses nearby"],
        "sources": ["elephant_cbe", "elephant_buffer"],
    },
    "Bonnet macaque": {
        "where": "villages, groves and forest edge",
        "raids": ["Banana", "Coconut", "Maize", "Groundnut", "Sugarcane"],
        "evidence": "general",
        "note": "Takes ripening fruit and cobs and pulls up groundnut pods; coconut tender nuts.",
        "when": "fruit and cob ripening, pod stage of groundnut",
        "deterrents": ["Netting over high-value plots", "Cover harvested produce and storage", "Sound and scare devices, varied often",
                       "Fodder or a distraction strip at the buffer edge", "Do not feed troops"],
        "sources": ["monkey", "kfri"],
    },
    "Peafowl": {
        "where": "open fields near scrub and forest",
        "raids": ["Groundnut", "Chilli", "Blackgram", "Maize", "Rice"],
        "evidence": "general",
        "note": "Pecks emerging seedlings, pods and ripe fruit; a protected bird, so use scaring, not harm.",
        "when": "seedling emergence and ripening",
        "deterrents": ["Reflective tape lines 1 to 1.5 m high", "Bird net over seed beds", "Row covers for seedlings", "Scare devices at dawn and dusk"],
        "sources": ["icar", "kfri"],
    },
    "Deer (sambar, spotted deer)": {
        "where": "forest edge and scrub",
        "raids": ["Groundnut", "Blackgram", "Cotton", "Rice", "Maize"],
        "evidence": "general",
        "note": "Browses young shoots and legumes; cotton and pulses at the seedling stage.",
        "when": "seedling and early vegetative stages",
        "deterrents": ["Fence or bio-fence (agave or cactus in double rows) on vulnerable borders", "Motion lights and alarms at dusk and night", "Repellent sprays on boundary rows"],
        "sources": ["icar", "kfri"],
    },
    "Stray cattle": {
        "where": "village roads and valley fields",
        "raids": ["Rice", "Maize", "Sugarcane", "Banana", "Blackgram", "Groundnut"],
        "evidence": "general",
        "note": "Mostly a valley-bottom problem.",
        "when": "young crop stages",
        "deterrents": ["Thorny live fence or bund", "Community arrangements for stray animals with the panchayat"],
        "sources": ["icar"],
    },
}

# crops the published studies describe as unpalatable, or less attractive, to the big raiders
LESS_ATTRACTIVE = {
    "Chilli": "The best-documented deterrent crop: chilli buffers are reported to keep elephants out. The evidence for other animals is not established here, and peafowl can still peck chilli seedlings and fruit.",
    "Turmeric": "Reported as less attractive to elephants. Rhizome crops such as ginger are reported dug up by wild boar in the Western Ghats, so treat turmeric as at risk from boar.",
}
NOT_SAFE = {  # crops where the evidence says the opposite
    "Maize": "A favourite of wild boar, macaques and peafowl.",
    "Groundnut": "Wild boar root up pods; macaques, peafowl and deer also take it.",
    "Banana": "Elephants, boar and macaques all raid banana.",
    "Sugarcane": "Elephants and wild boar raid sugarcane, especially near harvest.",
}

# animals expected per zone, with a baseline level. Foothill parcels sit at the forest edge.
ZONE_BASE = {
    "foothill": {"Wild boar": 2, "Elephant": 1, "Bonnet macaque": 2, "Peafowl": 1, "Deer (sambar, spotted deer)": 1, "Stray cattle": 0},
    "terrace": {"Wild boar": 1, "Elephant": 0, "Bonnet macaque": 1, "Peafowl": 1, "Deer (sambar, spotted deer)": 0, "Stray cattle": 1},
    "valley": {"Wild boar": 0, "Elephant": 0, "Bonnet macaque": 0, "Peafowl": 1, "Deer (sambar, spotted deer)": 0, "Stray cattle": 2},
}
LEVEL = {0: "unlikely", 1: "low", 2: "medium", 3: "high"}


_PHOTO_KEY = {"Wild boar": "wild_boar", "Elephant": "elephant", "Bonnet macaque": "macaque", "Peafowl": "peafowl", "Deer (sambar, spotted deer)": "sambar", "Stray cattle": "cattle_cbe"}
_PHOTO_NOTE = {"wild_boar": "Ground rooted up by wild boar", "elephant": "Asian elephant", "macaque": "Bonnet macaque", "peafowl": "Indian peafowl", "sambar": "Sambar deer", "cattle_cbe": "Cattle grazing in an open field near Coimbatore"}


def _photo(name: str) -> dict | None:
    """Licensed Wikimedia Commons photo of the animal (one shows real boar rooting damage), with its credit."""
    key = _PHOTO_KEY.get(name)
    try:
        c = json.loads((config.DATA_DIR / "images" / "wildlife" / "credits.json").read_text(encoding="utf-8"))[key]
    except Exception:  # noqa: BLE001
        return None
    return {"url": f"/images/{c['file']}", "caption": _PHOTO_NOTE[key] + (" (damage to a field)" if key == "wild_boar" else " (to recognise the animal; not damage)"),
            "credit": f"{c['author']}, {c['license']}", "page": c["page"]}



def parcel_risk(crop: str, zone: str, recorded: dict | None = None) -> dict:
    """Animals likely at one parcel, most likely first, each with why and what to do."""
    base = ZONE_BASE.get(zone, ZONE_BASE["terrace"])
    rows = []
    for name, a in ANIMALS.items():
        score = base.get(name, 1)
        crop_hit = crop in a["raids"]
        if crop_hit:
            score += 1
        elif score > 0:
            score -= 1
        if a.get("evidence", "general") != "strong":
            score = min(score, 2)                     # only the well-studied raiders (boar, elephant) are ever rated "high"
        score = max(0, min(3, score))
        why = []
        why.append(f"{zone} zone" + (" is at the forest edge" if zone == "foothill" else ""))
        why.append(f"{crop} is reported raided by this animal" if crop_hit else f"{crop} is not among the crops most reported raided by this animal")
        rows.append({"animal": name, "level": LEVEL[score], "score": score, "where": a["where"], "why": "; ".join(why),
                     "evidence": a.get("evidence", "general"), "crop_note": a["note"] if crop_hit else None, "vulnerable_when": a["when"] if crop_hit else None,
                     "deterrents": a["deterrents"], "sources": [SOURCES[k] for k in a["sources"]], "photo": _photo(name)})
    rows.sort(key=lambda r: -r["score"])
    return {
        "crop": crop, "zone": zone,
        "animals": rows,
        "crop_standing": LESS_ATTRACTIVE.get(crop) or NOT_SAFE.get(crop),
        "recorded_intrusion": recorded,
        "kind": "rule-based indication from published crop-raiding studies and the parcel's zone, not an observation",
        "evidence_note": ("Evidence is strong for wild boar and elephant (Tamil Nadu and Western Ghats studies). For macaque, peafowl, deer and stray cattle the crop lists are typical patterns "
                          "reported across India, not a Tenkasi study."),
        "note": ("This is an indication, not a guarantee: no crop is raid-proof and animal movement changes by season. Ask the village or Forest "
                 "Department about recent sightings, and report damage so compensation can be claimed. Recorded intrusion on the parcel is dummy data."),
    }


def general_answer(q: str) -> dict | None:
    """Answer a general wildlife question that names no parcel: which crops are raided or avoided, and how to protect a field."""
    import re
    low = q.lower()
    named: list[str] = []
    if re.search(r"\b(elephant|aanai|yaanai)\b", low):
        named = ["Elephant"]
    elif re.search(r"\b(boar|pig|panni)\b", low):
        named = ["Wild boar"]
    elif re.search(r"\b(monkey|macaque|kurangu)\b", low):
        named = ["Bonnet macaque"]
    elif re.search(r"\b(peacock|peafowl|mayil)\b", low):
        named = ["Peafowl"]
    elif re.search(r"\b(deer|sambar)\b", low):
        named = ["Deer (sambar, spotted deer)"]
    elif re.search(r"\b(cow|cows|cattle|bull|bulls|stray)\b", low):
        named = ["Stray cattle"]
    if not named:
        named = ["Wild boar", "Elephant", "Bonnet macaque", "Peafowl"]
    out = []
    for n in named[:4]:
        a = ANIMALS[n]
        out.append(f"{n}: reported to raid {', '.join(a['raids'][:5]).lower()}. {a['note']} Protect with: {'; '.join(a['deterrents'][:3]).lower()}.")
    less = "; ".join(f"{c}: {t}" for c, t in LESS_ATTRACTIVE.items())
    return {"text": " ".join(out) + f" Crops reported as less attractive: {less} " + "No crop is raid-proof; report damage to the Forest Department.",
            "sources": [SOURCES[k] for n in named[:4] for k in ANIMALS[n]["sources"]],
            "animals": [{"animal": n, "photo": _photo(n)} for n in named[:4] if _photo(n)]}
