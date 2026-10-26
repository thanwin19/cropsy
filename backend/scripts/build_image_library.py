"""build_image_library.py: a local library of licensed farming photographs from Wikimedia Commons (data/images/library + data/images/library.json).

For each topic the Commons search is queried, and only files with an open licence that allows reuse with attribution (CC0, public domain, CC BY, CC BY-SA) are kept. Each is
downloaded once (800 px), de-duplicated by content hash, and recorded with author, licence, source page and the search it came from. A person then looks at every photo
(contact sheets) and removes any that is irrelevant or shows the wrong thing: this script never decides relevance by itself.
Usage: python scripts/build_image_library.py [--only topic_id]"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests

S = requests.Session()
S.headers["User-Agent"] = "CropsyDemo/1.0 (educational farm advisory; contact: see repository)"
ROOT = Path(__file__).resolve().parent.parent / "data" / "images" / "library"
CAT = ROOT.parent / "library.json"
OK_LIC = re.compile(r"^(CC0|Public domain|PD|CC BY(-SA)? \d(\.\d)?( [A-Za-z]{2}| [A-Za-z ]+)?)$", re.I)
BAD = re.compile(r"\bNC\b|-NC|-ND|fair use|non-?commercial|no derivatives", re.I)

# id: (search query, words a question would use, label)
TOPICS = {
    "fall_armyworm": ("Spodoptera frugiperda larva maize", "fall armyworm spodoptera maize", "Fall armyworm larva on maize"),
    "pod_borer": ("Helicoverpa armigera larva", "pod borer helicoverpa gram redgram cotton bollworm", "Helicoverpa (pod borer) caterpillar"),
    "leaf_folder": ("Cnaphalocrocis medinalis rice leaf folder", "leaf folder rice paddy", "Rice leaf folder"),
    "brinjal_borer": ("Leucinodes orbonalis brinjal fruit borer", "brinjal eggplant shoot fruit borer", "Brinjal shoot and fruit borer"),
    "pink_bollworm": ("pink bollworm Pectinophora gossypiella cotton", "pink bollworm cotton", "Pink bollworm on cotton"),
    "red_palm_weevil": ("red palm weevil Rhynchophorus ferrugineus coconut", "red palm weevil coconut palm", "Red palm weevil"),
    "coconut_mite": ("coconut eriophyid mite damage nuts", "coconut mite eriophyid", "Coconut mite damage"),
    "tomato_leaf_curl": ("tomato yellow leaf curl virus", "tomato leaf curl virus whitefly", "Tomato leaf curl virus symptoms"),
    "tomato_fruit_borer": ("tomato fruit borer caterpillar", "tomato fruit borer", "Fruit borer caterpillar on tomato"),
    "powdery_mildew": ("powdery mildew on leaves", "powdery mildew fungus white powder", "Powdery mildew on a leaf"),
    "bacterial_blight": ("bacterial leaf blight rice Xanthomonas oryzae", "bacterial leaf blight rice", "Bacterial leaf blight of rice"),
    "banana_bunchy_top": ("banana bunchy top virus", "banana bunchy top virus", "Banana bunchy top virus"),
    "panama_wilt": ("Fusarium wilt banana Panama disease", "panama wilt fusarium banana", "Panama wilt of banana"),
    "n_deficiency": ("nitrogen deficiency leaf yellowing", "nitrogen deficiency yellow leaves", "Nitrogen deficiency (yellowing leaves)"),
    "p_deficiency": ("phosphorus deficiency leaf purple", "phosphorus deficiency purple leaves", "Phosphorus deficiency (purple leaves)"),
    "zinc_deficiency": ("zinc deficiency rice khaira", "zinc deficiency rice khaira", "Zinc deficiency in rice"),
    "rice_nursery": ("rice nursery seedlings", "rice nursery seedbed seedlings paddy", "Rice nursery seedlings"),
    "rice_transplanting": ("rice transplanting machine", "rice transplanter transplanting paddy", "Rice transplanting"),
    "seed_treatment": ("seed treatment seeds treated fungicide", "seed treatment", "Treated seed"),
    "soil_profile": ("soil profile horizons", "soil profile layers horizon", "Soil profile"),
    "soil_sampling": ("soil sampling auger", "soil sample sampling auger", "Soil sampling"),
    "tractor_plough": ("tractor plough India field", "tractor plough ploughing tillage", "Tractor ploughing"),
    "paddy_harvest": ("combine harvester rice paddy India", "harvester harvest paddy rice", "Rice harvest"),
    "power_tiller": ("power tiller India", "power tiller", "Power tiller"),
    "drip_emitter": ("drip irrigation emitter dripper", "drip emitter dripper irrigation", "Drip emitter"),
    "sprinkler": ("sprinkler irrigation field", "sprinkler irrigation", "Sprinkler irrigation"),
    "furrow_irrigation": ("furrow irrigation field", "furrow irrigation flood", "Furrow irrigation"),
    "plastic_mulch": ("plastic mulch vegetables field", "mulch mulching plastic film", "Plastic mulch"),
    "compost_pit": ("compost pit farm", "compost pit heap manure", "Compost pit"),
    "green_manure": ("green manure sesbania dhaincha", "green manure sesbania dhaincha sunnhemp", "Green manure crop"),
    "azolla": ("Azolla biofertilizer rice", "azolla biofertilizer", "Azolla"),
    "yellow_sticky_trap": ("yellow sticky trap insects greenhouse", "yellow sticky trap whitefly aphid", "Yellow sticky trap"),
    "light_trap": ("light trap insect agriculture", "light trap insects", "Insect light trap"),
    "farm_pond": ("farm pond India water harvesting", "farm pond rainwater harvesting", "Farm pond"),
    "rain_gauge": ("rain gauge", "rain gauge rainfall measure", "Rain gauge"),
    "weather_station": ("automatic weather station agriculture", "weather station", "Weather station"),
    "wheat_field": ("wheat field ears", "wheat crop", "Wheat crop"),
    "ragi": ("finger millet Eleusine coracana plant", "ragi finger millet", "Finger millet (ragi)"),
    "sorghum": ("sorghum crop field India", "sorghum cholam jowar", "Sorghum crop"),
    "pearl_millet": ("pearl millet field bajra", "pearl millet bajra cumbu", "Pearl millet"),
    "groundnut": ("groundnut plant pods Arachis hypogaea", "groundnut peanut pods", "Groundnut plant with pods"),
    "sesame": ("sesame plant Sesamum indicum", "sesame gingelly til", "Sesame plant"),
    "castor": ("castor plant Ricinus communis", "castor plant", "Castor plant"),
    "sunflower": ("sunflower field", "sunflower", "Sunflower field"),
    "soybean": ("soybean plant pods", "soybean soya", "Soybean plant"),
    "cowpea": ("cowpea plant pods Vigna unguiculata", "cowpea", "Cowpea"),
    "bengal_gram": ("chickpea plant Cicer arietinum", "bengal gram chickpea gram", "Chickpea (Bengal gram)"),
    "redgram": ("pigeon pea Cajanus cajan plant", "redgram pigeon pea tur arhar", "Pigeon pea (redgram)"),
    "turmeric": ("turmeric rhizome Curcuma longa", "turmeric rhizome", "Turmeric rhizomes"),
    "chilli": ("chilli pepper plant fruits Capsicum annuum", "chilli pepper", "Chilli plant"),
    "tomato_plant": ("tomato plant fruits field staking", "tomato plant", "Tomato plant"),
    "brinjal_plant": ("brinjal eggplant plant fruit", "brinjal eggplant aubergine", "Brinjal plant"),
    "onion_bulbs": ("onion bulbs harvest India", "onion bulb", "Onion bulbs"),
    "okra": ("okra plant Abelmoschus esculentus fruit", "okra lady finger bhendi", "Okra plant"),
    "sugarcane_field": ("sugarcane field India", "sugarcane field crop", "Sugarcane field"),
    "coconut_palms": ("coconut palm plantation India", "coconut palm tree", "Coconut palms"),
    "banana_plantation": ("banana plantation India bunch", "banana plantation bunch", "Banana plantation"),
    "cotton_boll": ("cotton plant open boll", "cotton boll plant", "Cotton boll"),
    "maize_field": ("maize field cobs", "maize corn field cobs", "Maize crop"),
    "neem": ("neem tree leaves Azadirachta indica", "neem tree leaves oil seed kernel", "Neem leaves"),
    "earthworm": ("earthworm Eisenia fetida", "earthworm vermicompost worms", "Composting earthworms"),
    "weeds_rice": ("weeds in paddy field", "weeds weed control paddy", "Weeds in a paddy field"),
    "hand_weeding": ("weeding by hand farmers India field", "hand weeding weeder", "Hand weeding"),
    "knapsack_sprayer": ("knapsack sprayer farmer India", "knapsack sprayer spray pesticide safety", "Knapsack sprayer"),
}


def search(q: str, n: int = 8) -> list[dict]:
    r = S.get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "generator": "search", "gsrsearch": q + " filetype:bitmap", "gsrnamespace": 6, "gsrlimit": n,
              "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 800, "format": "json"}, timeout=40).json()
    out = []
    for p in (r.get("query", {}).get("pages", {}) or {}).values():
        ii = p.get("imageinfo", [{}])[0]
        m = ii.get("extmetadata", {})
        lic = (m.get("LicenseShortName", {}).get("value") or "").strip()
        if not lic or BAD.search(lic) or not OK_LIC.match(lic):
            continue
        if ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 500:
            continue
        out.append({"title": p["title"], "thumb": ii.get("thumburl"), "license": lic, "author": re.sub(r"<[^>]+>", "", m.get("Artist", {}).get("value", "")).strip()[:80] or "unknown",
                    "page": ii.get("descriptionurl"), "index": p.get("index", 99)})
    return sorted(out, key=lambda x: x["index"])


def main() -> None:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    ROOT.mkdir(parents=True, exist_ok=True)
    cat = json.loads(CAT.read_text(encoding="utf-8")) if CAT.exists() else {}
    hashes = {v["sha"] for v in cat.values()}
    for tid, (q, words, label) in TOPICS.items():
        if only and tid != only:
            continue
        got = 0
        try:
            cands = search(q)
        except Exception as e:  # noqa: BLE001
            print("search failed", tid, e)
            continue
        for c in cands:
            if got >= 2:
                break
            iid = f"{tid}_{got + 1}"
            if iid in cat:
                got += 1
                continue
            try:
                b = S.get(c["thumb"], timeout=60).content
            except Exception:  # noqa: BLE001
                continue
            sha = hashlib.sha1(b).hexdigest()
            if len(b) < 8000 or sha in hashes:
                continue
            hashes.add(sha)
            ext = "png" if b[:4] == b"\x89PNG" else "jpg"
            (ROOT / f"{iid}.{ext}").write_bytes(b)
            cat[iid] = {"id": iid, "topic": tid, "file": f"library/{iid}.{ext}", "label": label, "words": words, "license": c["license"], "author": c["author"], "page": c["page"],
                        "title": c["title"], "query": q, "sha": sha, "bytes": len(b), "reviewed": False}
            got += 1
        print(tid, got)
        time.sleep(0.3)
    CAT.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(cat), "images in the catalog")


if __name__ == "__main__":
    main()
