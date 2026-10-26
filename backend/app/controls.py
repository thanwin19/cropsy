"""
controls.py — Curated pest/disease controls and organic nutrient options, quoted VERBATIM from the TNAU guides.

Automatic extraction from the guides is unsafe: their tables run neighbouring diseases together (an early prototype attached a
fungicide to rice tungro, a virus). So every entry here was read against the source text and is resolved by an anchor phrase;
the text shown to the user is the guide's own wording plus its page. tests/test_controls.py fails if an anchor stops resolving.

An issue with no entry here is reported as "no verified advice" and the farmer is sent to Cropsy or the KVK. Never guess.
"""
from __future__ import annotations

import re
from typing import Any

from app.steps import retrieve

CAUTION = ("Quoted from TNAU's 2020 guides. Confirm that a product is currently registered (CIB&RC) and follow its label before "
           "use. These are not a diagnosis: check the problem first.")

# kind: cultural | chemical | organic | schedule(mixed list of products) | fertiliser
# find: regex locating the passage (whitespace collapsed); end: regex marking where it stops (optional); t: use group "t" if present
C = lambda kind, find, end=None: {"kind": kind, "find": find, "end": end}  # noqa: E731

CONTROLS: dict[str, dict[str, Any]] = {
    "rice_blast": {"crop": "Rice", "items": [
        C("cultural", r"Avoid excess nitrogen", r"(?= Use resistant varieties)"),
        C("cultural", r"Use resistant varieties like CO 47", r"(?= 2\. Chemical method)"),
        C("chemical", r"Spray carbendazim 50WP @ 500 g/ha or tricyclozole 75 WP @ 500 g/ha", r"(?= •| CIB| Biological)"),
        C("organic", r"Treat the seeds with talc based formulation of Pseudomonas fluorescens @ 10g/kg of seed", r"(?= and soak| •)"),
    ]},
    "rice_sheath_blight": {"crop": "Rice", "items": [
        C("organic", r"Apply neem cake @ 150 kg/ha to soil", r"(?= Chemical method)"),
        C("chemical", r"Spray carbendazim @ 500 g/ha or metominostrobin @ 500 ml/ha or hexaconazole 75% WG @ 100 mg/ lit\. First spray at the time of disease appearance and second spray at 15 days later", r"(?= Biological control)"),
        C("organic", r"Treat the seeds with Pseudomonas fluorescens TNAU liquid formulation @ 10 ml/kg of seeds", r"(?= •)"),
    ]},
    "rice_narrow_brown_spot": {"crop": "Rice", "closest": "TNAU lists brown spot (Drechslera oryzae), the closest listed disease. Narrow brown leaf spot itself is not listed.", "items": [
        C("chemical", r"Spray metominostrobin @ 500 ml/ha after observing initial infection of the disease", r"(?= CIB)"),
    ]},
    "rice_tungro": {"crop": "Rice", "closest": "Tungro is a virus spread by leafhoppers: control the vector. TNAU also lists vector insecticides on page 72; check their current registration before using any.", "items": [
        C("cultural", r"Set up light traps to attract and control the leaf hopper vectors as well as to monitor the population", r"(?= •)"),
    ]},
    "banana_sigatoka": {"crop": "Banana", "items": [
        C("cultural", r"Remove affected leaves and burn", r"(?= Spray carbendazim)"),
        C("chemical", r"Spray carbendazim @ 1 g/l or benomyl @ 1 g/l or mancozeb @ 2 g/l", r"(?= Alternatively)"),
        C("organic", r"Pseudomonas fluorescens @ 0\.5% three times at 15 days interval", r"(?= to control)"),
    ]},
    "cane_red_rot": {"crop": "Sugarcane", "items": [
        C("cultural", r"Selection of setts from healthy nursery programme", r"(?= •)"),
        C("chemical", r"Sett treatment with carbendazim before planting", r"(?= •)"),
        C("cultural", r"The irrigation interval in red rot affected field must be lengthened", r"(?= • Removal)"),
    ]},
    "cane_rust": {"crop": "Sugarcane", "items": [
        C("chemical", r"Rust: Puccinia melanocephala\s*•\s*(?P<t>\w*pray mancozeb @ 2 kg/ha)"),
    ]},
    "cane_yellow_leaf": {"crop": "Sugarcane", "items": [
        C("cultural", r"Yellow leaf disease: Sugarcane yellow leaf virus \(Vector: Melanopsis sacchari\)\s*•\s*(?P<t>\w*se of disease free setts for planting.*?)(?= General Recommendations)"),
    ]},
    "cane_mosaic": {"crop": "Sugarcane", "closest": "TNAU gives no mosaic-specific chemical. Control is by clean planting material.", "items": [
        C("cultural", r"select healthy setts for planting; in the seed crop select plants that do not show symptoms of red rot, smut, grassy shoot and ratoon stunting", r"(?= The source)"),
    ]},
    # ── added crops (groundnut, cotton, blackgram, chilli, turmeric): verbatim TNAU 2020 guide passages ──
    "groundnut_rust": {"crop": "Groundnut", "items": [
        C("chemical", r"Spray mancozeb @ 1000 g /ha or chlorothalonil @ 1000 g /ha or wettable sulphur @ 2500 g /ha\. If necessary, repeat the spray 15 days later", r"(?= Early leaf spot)"),
        C("organic", r"spray 10% Calotropis leaf extract", r"(?= or spray carbendazim)"),
    ]},
    "groundnut_leaf_spot": {"crop": "Groundnut", "items": [
        C("chemical", r"Spray carbendazim @ 500 g/ha or mancozeb @ 1000 g/ha or chlorothalonil @ 1000 g/ha\. If necessary, repeat the spray 15 days later", r"(?= CIB)"),
    ]},
    "groundnut_root_rot": {"crop": "Groundnut", "items": [
        C("organic", r"Soil application of P\. fluorescens @ 2\.5 kg /ha with 50 kg of well decomposed FYM / sand", r"(?= at 3|\.)"),
    ]},
    "cotton_bacterial_blight": {"crop": "Cotton", "items": [
        C("cultural", r"Avoid stacking of infected plants", r"(?= •| Spray)"),
        C("chemical", r"Spray streptomycin sulphate @ 300 ppm \+ copper oxychloride @ 2\.0 kg/ha immediately after the symptom appearance and repeat at 10 days later", r"(?=\. Alternaria| Alternaria|\.)"),
    ]},
    "cotton_alternaria_leaf_spot": {"crop": "Cotton", "items": [
        C("chemical", r"Copper oxychloride @ 2 kg or mancozeb @ 1 kg or chlorothalonil @ 500 g/ha", r"(?= or difenaconazole)"),
    ]},
    "cotton_wilt": {"crop": "Cotton", "items": [
        C("organic", r"Seed treatment with Pseudomonas fluorescens \+ Bacillus s u b t i l i s \+ Trichoderma asperellum mixture @ 10 g/kg", r"(?= and soil application)"),
    ]},
    "blackgram_yellow_mosaic": {"crop": "Blackgram", "closest": "Yellow mosaic is a virus spread by whitefly: TNAU stresses resistant varieties and vector control, not a fungicide.", "items": [
        C("cultural", r"Growing resistant varieties such as VBN 4, VBN 6, VBN 7 and VBN8", r"(?= •)"),
        C("cultural", r"Installation of yellow sticky traps @ 12 numbers / ha", r"(?= •)"),
    ]},
    "blackgram_powdery_mildew": {"crop": "Blackgram", "items": [
        C("organic", r"Spray NSKE 5% or neem oil 3% twice at 10 days interval from initial disease symptom appearance", r"(?= •)"),
        C("chemical", r"Spray carbendazim @ 500 g or wettable sulphur 1500 g/ha or propiconazole 500 ml/ha at initiation of the disease and 10 days later", r"(?= Rust)"),
    ]},
    "blackgram_rust": {"crop": "Blackgram", "items": [
        C("chemical", r"Spray mancozeb @ 1000 g or wettable sulphur 1500 g /ha at initiation of the disease and 10 days later", r"(?= Leaf spot)"),
    ]},
    "blackgram_leaf_spot": {"crop": "Blackgram", "items": [
        C("chemical", r"Spray carbendazim @ 500 g/ha or mancozeb @ 1000g /ha at initiation of the disease and 10 days later", r"(?= Yellow mosaic)"),
    ]},
    "chilli_leaf_spot": {"crop": "Chilli", "items": [
        C("chemical", r"Spray mancozeb @ 2 g/l or copper oxychloride @ 2\.5 g/l", r"(?= Powdery mildew)"),
    ]},
    "chilli_powdery_mildew": {"crop": "Chilli", "items": [
        C("chemical", r"Spray wettable sulphur @ 3 g/l or carbendazim @ 1 g/l three sprays at 15 days interval from the first appearance of symptoms", r"(?= CIB)"),
    ]},
    "chilli_anthracnose": {"crop": "Chilli", "items": [
        C("chemical", r"Anthracnose\s*•\s*(?P<t>Spray mancozeb @ 2 g/l)(?= Die-back)"),
    ]},
    "chilli_die_back_fruit_rot": {"crop": "Chilli", "items": [
        C("chemical", r"Spray mancozeb @ 2 g/l or copper oxychloride @ 2\.5 g/l thrice at 15 days interval starting from noticing the die-back symptoms", r"(?= CIB)"),
    ]},
    "turmeric_rhizome_rot": {"crop": "Turmeric", "items": [
        C("chemical", r"Treat the seed rhizomes with copper oxychloride @ 0\.3% for 30 minutes or drench with 1% Bordeaux mixture or copper oxychloride @ 0\.25 %", r"(?= or metalaxyl)"),
        C("organic", r"Seed treatment with P\. fluorescens @ 10 g/kg or T\. asperellum @ 4 g/kg of rhizome", r"(?= and soil application)"),
    ]},
    "turmeric_leaf_spot": {"crop": "Turmeric", "items": [
        C("chemical", r"Spray carbendazim @ 500 g/ha or mancozeb @ 1 kg/ha or copper oxychloride @ 1\.25 kg/ha or propiconazole @ 500 ml/ha", r"(?= Harvest)"),
    ]},
    "maize_fall_armyworm": {"crop": "Maize", "items": [
        C("organic", r"Apply neem cake @ 250 kg/ha during last ploughing and treat seeds with thiamethoxam 30 FS or Beauveria bassiana @ 10 g/ kg"),
        C("cultural", r"Use solar light trap @ one /ha and sex pheromone traps @ 50/ha for mass trapping of adults from 10-15 DAS", r"(?= Apply any one)"),
        C("schedule", r"Early whorl stage \(15 – 20 DAS\) • Azadirachtin 1% EC 20 ml/10 l • Thiodicarb 75 WP 20 g/10 l • Emamectin benzoate 5 SG 4g/10 l", r"(?= • Late whorl)"),
    ]},
    "maize_leaf_blight": {"crop": "Maize", "items": [
        C("chemical", r"Spray mancozeb or zineb @ 2-4 g/l on appearance of the disease and repeat at 10 days interval, if necessary", r"(?= •| Seed treatment)"),
        C("organic", r"Seed treatment with Pseudomonas fluorescens @ 10g/ kg", r"(?= and spray)"),
    ]},
    "maize_n_deficiency": {"crop": "Maize", "items": [
        C("fertiliser", r"Apply half of N and full dose of P2 O5 and K2 O with enriched FYM as basal along with Azospirillum \(10 packets/ha\)\. iii\. Top dress remaining half of N at tasseling", r"(?= Soil test)"),
    ]},
    "coconut_bud_rot": {"crop": "Coconut", "items": [
        C("cultural", r"Infected tissues of the bud should be scooped off and treated with Bordeaux paste", r"(?= Destruction)"),
        C("chemical", r"Drenching crowns of surrounding healthy palms with 1% Bordeaux mixture", r"(?= Foot rot)"),
    ]},
    "coconut_leaf_rot": {"crop": "Coconut", "items": [
        C("cultural", r"remove the rotten portions from the spear and the two adjacent leaves", r"(?=\.)"),
        C("chemical", r"Pour hexaconazole 2 ml or mancozeb 3 g in 300 ml water per palm at the base of the spindle leaf", r"(?=;|\.)"),
    ]},
    "coconut_gray_leaf_spot": {"crop": "Coconut", "closest": "TNAU lists a general coconut 'leaf spot'; gray leaf spot itself is not named.", "items": [
        C("chemical", r"Leaf spot\s*•?\s*Foliar spray with 1% bordeaux mixture or mancozeb @ 0\.2 %", r"(?= Harvest)"),
    ]},
    "coconut_k_deficiency": {"crop": "Coconut", "items": [
        C("fertiliser", r"Muriate of potash \(1200 g K2O\) in two equal splits during June – July and December – January", r"(?=\.)"),
    ]},
    "banana_k_deficiency": {"crop": "Banana", "items": [
        C("fertiliser", r"Apply N and K in 3 splits on 3rd, 5th and 7th month", r"(?=,? Phosphorus| Apply)"),
    ]},
}

# Weed control per crop, verbatim. Banana has no usable weed passage in the guides, so it is deliberately absent.
WEEDS: dict[str, list[dict]] = {
    "Rice": [C("chemical", r"Use Butachlor 1\.25kg/ha or Anilophos 0\.4kg/ha as pre-emergence application", r"(?= Alternatively)"),
             C("chemical", r"Alternatively, pre-emergence application of herbicide mixture viz\., Butachlor 0\.6kg \+ 2,4 DEE 0\.75kg/ha", r"(?= will have)"),
             C("cultural", r"Any herbicide has to be mixed with 50kg of dry sand on the day of application", r"(?= •|\.)")],
    "Maize": [C("chemical", r"Atrazine @ 0\.50 – 0\.75 kg/ha as pre-emergence on 3-5 DAS", r"(?= \(or\))")],
    "Sugarcane": [C("chemical", r"Atrazine 1 kg or Oxyflurofen 750 ml/ha mixed in 500 liters of water as pre emergence herbicide on the 3rd day of planting", r"(?= iii\.)")],
    "Groundnut": [C("chemical", r"Pre-emergence: Pendimethalin @ 1\.0 litre/ha applied through flat fan nozzle with 500 l of water/ha\. After 35 - 40 days one hand weeding may be given", r"(?=\. ii\))")],
    "Cotton": [C("chemical", r"Pre-emergence application of Pendimethalin 1\.0 litre/ha ensures weed free condition for 40 - 45 days\. This should be followed by one hand weeding and earthing up during 40 - 45 days", r"(?=\. ii\)|\.)")],
    "Blackgram": [C("chemical", r"Pre emergence application of Pendimethalin 1\.0 litres/ha under irrigated condition", r"(?= using Backpack| \()"),
                  C("cultural", r"If herbicides are not applied give two hand weedings on 15 and 30 days after sowing", r"(?=\. ii\)|\.)")],
    "Chilli": [C("chemical", r"Apply Pendimethalin 1\.0 kg a\.i\. / ha or Fluchloralin 1\.0 kg a\.i\. / ha as pre-emergence herbicide followed by hand weeding once 30 days after planting", r"(?= Irrigation)")],
    "Coconut": [C("cultural", r"The interspace in the coconut garden has to be ploughed twice in a year in June-July and December - January", r"(?=\.)")],
}

# Organic / bio nutrient options per crop (FYM, compost, bio-fertilisers), also verbatim
ORGANIC_NUTRIENTS: dict[str, list[dict]] = {
    "Rice": [C("organic", r"Apply a basal dose of 750 kg of FYM enriched with fertilizer phosphorus \(P at 25 kg/ha\)", r"(?= •)"),
             C("organic", r"Five packets \(1kg/ha\) each of Azospirillum and Phosphobacteria or five packets \(1kg/ha\) of Azophos bioinoculants", r"(?= are mixed)")],
    "Banana": [C("organic", r"mixed with 10 kg of FYM, 250 g of Neem cake", r"(?=\.)"),
               C("organic", r"Apply Azospirillum and Phosphobacteria 20 g each at planting and 5th month after planting", r"(?= preceding)")],
    "Coconut": [C("organic", r"apply 50g of Azospirillum, 50 g of Phosphobacteria \(or\) 50 g of Azophos and 50 g of AM fungi", r"(?= Mix all)")],
    "Sugarcane": [C("organic", r"Apply FYM at 12\.5 t/ha or compost 25 t/ha or filter press mud at 37\.5 t/ha before the last ploughing under gardenland conditions", r"(?= In wetlands)")],
    "Groundnut": [C("organic", r"Treat one hectare of seeds with 125 ml of Rhizobium \(TNAU 14\) and 125 ml of Phosphobacteria", r"(?=, shade dry)")],
    "Cotton": [C("organic", r"Spread 12\.5 t of FYM or compost or 2\.5 t of vermicompost per ha if available, uniformly on the unploughed soil", r"(?=\.)")],
    "Blackgram": [C("organic", r"Treat the seeds required for sowing 1 ha with 200g each of Rhizobial culture COG 15, Phosphobacteria and PGPR", r"(?= using rice)")],
    "Chilli": [C("organic", r"Apply FYM @ 25 t / ha as basal before last ploughing", r"(?=\.)")],
    "Turmeric": [C("organic", r"Apply TNAU Micronutrient mixture @ 10kg/ha as in enriched FYM \(1:10 ratio\) at 50% basal and 50% on 90 DAP", r"(?= Top dressing)")],
    "Maize": [C("organic", r"Spread 12\.5 t/ha of FYM or compost or composted coir pith evenly on the unploughed field along with 10 packets of Azospirillum \(2000 g/ha\)", r"(?= and incorporate)")],
}

# Planting density quoted from TNAU (plants or hills per hectare). Imagery cannot count plants at 10 m, so this is spacing arithmetic.
PLANT_DENSITY = {
    "Coconut": dict(per_ha=175, unit="palms", find=r"spacing of 25' x 25' \(7\.5 x 7\.5 m\) with 175 plants/ha", note="7.5 x 7.5 m spacing"),
    "Banana": dict(per_ha={"Nendran": 5000, "default": 4600}, unit="plants",
                   find=r"1\.8 x 3\.6 m \(4600 plants / ha\) for Cavendish varieties and 2 m x 3 m for Nendran \(5000 plants / ha\)",
                   note="2 x 3 m for Nendran, 1.8 x 3.6 m for Cavendish types (Grand Naine)"),
    "Maize": dict(per_ha=66667, unit="plants", find=r"Adopt spacing of 60 x 25 cm for irrigated", note="60 x 25 cm (irrigated), 10,000 / (0.60 x 0.25)"),
    "Groundnut": dict(per_ha=333333, unit="plants", find=r"Adopt a spacing of 30 cm between rows and 10 cm between plants", note="30 x 10 cm, 10,000 / (0.30 x 0.10)"),
    "Blackgram": dict(per_ha=333333, unit="plants", find=r"For irrigated crop dibble the seeds adopting 30 x 10 cm spacing", note="30 x 10 cm (irrigated)"),
    "Chilli": dict(per_ha=37037, unit="plants", find=r"Spacing Varieties : 60 x 45 cm", note="60 x 45 cm for varieties, 10,000 / (0.60 x 0.45)"),
    "Turmeric": dict(per_ha=148148, unit="plants", find=r"Spacing 45 x 15 cm", note="45 x 15 cm, 10,000 / (0.45 x 0.15)"),
    "Rice": dict(per_ha=500000, unit="hills", find=r"20 x 10 \(50 hills/m2 \)", note="20 x 10 cm = 50 hills per m2"),
}

_DROPCAPS = [(r"^pray\b", "Spray"), (r"^se of\b", "Use of"), (r"\belection of\b", "Selection of"), (r"\broper nutritional\b", "Proper nutritional")]


def _clean(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip(" •-")
    parts = [p.strip() for p in t.split(" • ")]
    out = []
    for p in parts:
        for pat, rep in _DROPCAPS:                     # the guides' PDF drops the first letter of some bullets
            p = re.sub(pat, rep, p)
        out.append(p[:1].upper() + p[1:])
    return " · ".join(out)


def _find(crop: str, spec: dict) -> dict | None:
    retrieve._load_chunks()
    for c in retrieve._CHUNKS:
        if c.get("crop") != crop:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"[]", " • ", c.get("text") or ""))   # PDF bullet glyphs
        m = re.search(spec["find"], text, re.I | re.S)
        if not m:
            continue
        if "t" in m.groupdict() and m.group("t"):
            raw = m.group("t")
        else:
            raw = m.group(0)
            if spec.get("end"):
                e = re.search(spec["end"], text[m.end():])
                if e:
                    raw = text[m.start(): m.end() + e.start()]
        raw = raw[:380]
        return {"kind": spec["kind"], "text": _clean(raw), "source": f"{c.get('title', 'TNAU')} p.{c.get('page')}", "page": c.get("page"),
                "chunk_id": c.get("chunk_id"), "verified_source": c.get("dose_source", "pdf_text")}
    return None


def controls_for(issue_code: str | None) -> dict:
    spec = CONTROLS.get(issue_code or "")
    if not spec:
        return {"covered": False, "items": [], "caution": CAUTION,
                "note": "No verified TNAU control text for this problem is in the knowledge base. Ask Cropsy, or take it to your KVK."}
    items, missing = [], 0
    for it in spec["items"]:
        r = _find(spec["crop"], it)
        if r:
            items.append(r)
        else:
            missing += 1
    return {"covered": bool(items), "items": items, "unresolved": missing, "caution": CAUTION, "closest": spec.get("closest")}


def organic_nutrients(crop: str) -> list[dict]:
    return [r for r in (_find(crop, s) for s in ORGANIC_NUTRIENTS.get(crop, [])) if r]


def plant_estimate(crop: str, variety: str | None, area_ha: float) -> dict:
    spec = PLANT_DENSITY.get(crop)
    if not spec:
        return {"available": False, "note": "Not estimated: for this crop the TNAU spacing depends on variety or sett rate, and imagery at 10 m cannot count plants."}
    per_ha = spec["per_ha"]
    if isinstance(per_ha, dict):
        per_ha = per_ha["Nendran"] if (variety or "").lower().startswith("nendran") else per_ha["default"]
    src = _find(crop, {"kind": "spacing", "find": spec["find"], "end": None})
    return {"available": True, "per_ha": per_ha, "unit": spec["unit"], "total": round(per_ha * (area_ha or 0)), "area_ha": area_ha,
            "basis": f"TNAU planting density: {spec['note']}" + (f" ({src['source']})" if src else ""),
            "note": "Spacing arithmetic (area x recommended density). Satellite imagery at 10 m cannot count individual plants, so this is the expected stand, not a count."}


def weed_controls(crop: str) -> dict:
    items = [r for r in (_find(crop, sp) for sp in WEEDS.get(crop, [])) if r]
    if not items:
        return {"covered": False, "items": [], "caution": CAUTION,
                "note": "No verified TNAU weed-control text for this crop is in the knowledge base. Ask Cropsy or your KVK."}
    return {"covered": True, "items": items, "caution": CAUTION}
