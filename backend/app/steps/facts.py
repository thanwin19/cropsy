"""
facts.py: factual questions about a parcel (owner, area, soil, terrain, the 16 map layers, photo, location) are answered straight from
the data, with no language model, so every value is exact and every value says whether it is real, modelled or dummy.

The router sends a parcel question here when it asks for facts, not for treatment advice. The answer text lists only what was asked;
`state.facts` always carries the full record, which the chat card shows as a table with the photo.
"""
from __future__ import annotations

import json
import re
import time

from app import config, layers_api, wildlife
from app.schemas import PipelineState, TraceEntry

# topic -> words that ask for it
TOPICS: dict[str, str] = {
    "owner": r"\b(owner|owns|owned|ownership|patta|whose|farmer name|who is the farmer|belongs)\b",
    "area": r"\b(area|size|hectare|hectares|acre|acres|how big|how large)\b",
    "location": r"\b(location|coordinates|latitude|longitude|where is|where's|gps|survey|zone)\b",
    "soil": r"\b(soil ph|soil type|soil texture|texture|sand|clay|silt|ph value|drainage|soil(?!\s+moisture))\b",
    "terrain": r"\b(elevation|altitude|height above|slope|terrain|sunlight|sun hours|horizon|shade)\b",
    "layers": r"\b(ndvi|ndmi|ndwi|evi|savi|ndre|rvi|rsm|radar|moisture|evapotranspiration|water use|organic carbon|soc|land cover|landcover|"
              r"lulc|layers?|satellite|index|indices|greenness)\b",
    "photo": r"\b(photo|photos|picture|pictures|image|images|pic|snapshot)\b",
    "crop": r"\b(what crop|which crop|crop grown|variety|planted|planting date|growth stage|stage)\b",
    "management": r"\b(irrigation type|last irrigat\w*|last fertili[sz]\w*|fertili[sz]er programme|water ph)\b",
    "wildlife": r"\b(animals?|wildlife|boars?|pigs?|panni|elephants?|aanai|yaanai|monkeys?|macaques?|kurangu|deer|sambar|peacocks?|peafowl|mayil|raid\w*|intrusion|crop damage)\b",
    "price": r"\b(msp|price|prices|rate|market|mandi|sell|selling|support price|income|revenue|worth)\b",
    "all": r"\b(details|detail|information|info|profile|about|summary|tell me|everything|record)\b",
}
# a question that also asks what to DO is advice, not a fact lookup
ADVICE = re.compile(
    r"\b(spray|dose|dosage|how much (urea|dap|fertili[sz]er)|treat\w*|control|cure|manage|what should|should i|how to|advice|advise|"
    r"recommend\w*|irrigate today|need water|needs water|when to)\b",
    re.IGNORECASE,
)
_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in TOPICS.items()}


def topics_asked(q: str) -> list[str]:
    """Which fact topics a question asks for ([] if none, or if it is really asking for advice)."""
    if _COMPILED["wildlife"].search(q):
        return ["wildlife"] + [k for k, rx in _COMPILED.items() if k not in ("all", "wildlife") and rx.search(q)]   # "how do I protect it from boar" is still this lookup
    if ADVICE.search(q):
        return []
    hits = [k for k, rx in _COMPILED.items() if k != "all" and rx.search(q)]
    if not hits and _COMPILED["all"].search(q):
        return ["all"]
    return hits


# Minimum Support Price (CCEA, 2024-25 season). Only the crops that have an MSP; the rest are market-priced.
_MSP_ROWS = {"Rice": ["Paddy (Common)", "Paddy (Grade A)"], "Maize": ["Maize"], "Groundnut": ["Groundnut"], "Blackgram": ["Urad (Blackgram)"],
             "Cotton": ["Cotton (Medium)", "Cotton (Long)"]}


def _msp(crop: str, expected: dict | None) -> dict:
    try:
        rows = json.loads((config.DATA_DIR / "msp_2024_25.json").read_text(encoding="utf-8")).get("data", [])
    except Exception:  # noqa: BLE001
        rows = []
    want = _MSP_ROWS.get(crop)
    if not want or not rows:
        return {"has_msp": False, "note": f"{crop} has no Minimum Support Price in our data (it is market-priced). Check today's mandi rate on Agmarknet or with the local market committee."}
    found = [r for r in rows if r["crop"] in want]
    out = {"has_msp": True, "year": "2024-25", "rows": found,
           "note": "MSP for the 2024-25 season (CCEA). It is the government floor price, not today's market rate; check the current year's MSP and the mandi rate."}
    if expected and expected.get("mid") and expected.get("unit", "").startswith("t/ha") and found:
        q = float(expected["mid"]) * 10 * float(expected["area_ha"])      # tonnes per ha -> quintals for the whole parcel
        out["indicative_value_rs"] = round(q * found[0]["msp_rs_per_quintal"])
        out["indicative_basis"] = (f"{expected['mid']} {expected['unit']} (sample outlook from dummy yield history) x {expected['area_ha']} ha x Rs {found[0]['msp_rs_per_quintal']}/quintal "
                                   "(not a forecast or a guarantee)")
    return out


def _photo(p: dict, parcel_id: str) -> dict:
    """The parcel's own reference photo if one is on file, otherwise a clearly labelled representative photo of its crop."""
    manifest = config.DATA_DIR / "images" / "manifest.json"
    try:
        items = json.loads(manifest.read_text(encoding="utf-8")).get("items", [])
    except Exception:  # noqa: BLE001
        items = []
    tag = parcel_id.lower()
    own = next((i for i in items if i.get("condition_code") == "field_scene" and f"_{tag}_" in i["file"]), None)
    if own:
        return {"url": f"/images/{own['file']}", "kind": "parcel", "label": f"Reference photo supplied for {parcel_id} (health and stage unverified)"}
    crop = (p.get("crop") or {}).get("name")
    code = (p.get("observed_issue") or {}).get("code") or "healthy"
    pool = [i for i in items if i.get("crop") == crop and i.get("condition_code") == code and i.get("split") == "train"]         or [i for i in items if i.get("crop") == crop and i.get("condition_code") == "healthy" and i.get("split") == "train"]         or [i for i in items if i.get("crop") == crop and i.get("split") == "train" and i.get("condition_code") != "field_scene"]
    if pool:
        # every parcel gets its own sample photo: the parcel number picks the image, so neighbours growing the same crop differ
        n = int(re.sub(r"\D", "", parcel_id) or 0)
        rep = sorted(pool, key=lambda i: i["file"])[(n * 7) % len(pool)]
        return {"url": f"/images/{rep['file']}", "kind": "representative",
                "label": f"Sample photo (dummy): a {crop} leaf showing {str(rep.get('condition')).lower()}"
                         + (", matching this parcel's recorded condition." if rep.get("condition_code") == code else ".")
                         + f" It is not a photo of {parcel_id}."}
    return {"url": None, "kind": "none", "label": f"No photo of {parcel_id} is on file."}


def _expected(p: dict) -> dict | None:
    """Mid-point of the parcel's own last-three-season yields (same sample outlook the field report uses)."""
    try:
        from app import advisory_extras as ex
        y = ex.yield_outlook(p)
        return {"mid": y["expected_mid"], "unit": y["unit"], "area_ha": p.get("area_ha") or 0} if y else None
    except Exception:  # noqa: BLE001
        return None


def build(state: PipelineState) -> PipelineState:
    t0 = time.perf_counter()
    p = state.parcel_context or {}
    pid = p.get("parcel_id") or state.parcel_id
    if not pid:                                   # a general wildlife question that names no parcel
        g = wildlife.general_answer(state.query) or {"text": "", "sources": []}
        state.raw_answer = g["text"]
        state.recommendations = []
        state.limitations = (state.limitations or []) + ["General wildlife guidance from published studies; pick a parcel on the map for a parcel-specific indication."]
        state.facts = {"parcel_id": None, "wildlife_general": g}
        state.trace.append(TraceEntry(step="synthesize", tool_or_model="wildlife_general", why="General wildlife question: answered from the curated, sourced table",
                                      status="ok", latency_ms=(time.perf_counter() - t0) * 1000, est_cost_usd=0.0, input_summary=state.query[:80], output_summary="wildlife general"))
        return state
    loc = p.get("location") or {}
    layers = layers_api.lookup(loc.get("lat"), loc.get("lon")) if loc.get("lat") is not None else {"values": {}}
    vals = layers.get("values") or {}

    layer_rows = []
    for k, v in vals.items():
        if k == "tci":
            layer_rows.append({"id": k, "name": v["name"], "month": v["month"], "value": f"RGB {tuple(v['rgb'])}", "units": "", "kind": "real satellite data"})
            continue
        kind = "modelled" if k == "et" else "real satellite data"
        val = v.get("value")
        basis = "map pixel at the parcel centre"
        try:                                              # prefer the mean over every pixel inside the parcel boundary: a single centre pixel can differ from the field
            from app import field_analysis
            pm = field_analysis.parcel_layer_mean(pid, k, v["month"]) if v["month"] != "static" else None
            if pm and pm.get("mean") is not None:
                val, basis = pm["mean"], f"parcel mean of {pm['n_valid']} pixels"
        except Exception:  # noqa: BLE001
            pass
        layer_rows.append({"id": k, "name": v["name"], "month": v["month"], "value": "no clear data" if val is None else val,
                           "units": v.get("units", ""), "kind": kind, "basis": basis})

    crop = p.get("crop") or {}
    mgmt = p.get("management") or {}
    soil = p.get("soil") or {}
    terrain = p.get("terrain") or {}
    issue = p.get("observed_issue") or {}
    photo = _photo(p, pid)
    sat = state.satellite or {}

    facts = {
        "parcel_id": pid,
        "owner": {"name": (p.get("owner") or {}).get("name"), "patta_no": (p.get("owner") or {}).get("patta_no"), "kind": "dummy", "avatar": f"/images/owners/{pid}.svg"},
        "field_name": p.get("field_name"),
        "area_ha": p.get("area_ha"),
        "zone": p.get("zone"),
        "location": {"lat": loc.get("lat"), "lon": loc.get("lon"), "elevation_m": loc.get("elevation_m"), "kind": "real (DEM and survey coordinates)"},
        "crop": {"name": crop.get("name"), "variety": crop.get("variety"), "stage": crop.get("stage"),
                 "days_after_planting": crop.get("days_after_planting"), "planting_date": crop.get("planting_date"), "kind": "dummy"},
        "soil": {**soil, "kind": "dummy record (modelled values are in the layers table)"},
        "terrain": {**terrain, "kind": "real (Copernicus DEM, NOAA solar geometry)"},
        "management": {**mgmt, "kind": "dummy"},
        "recorded_issue": {"label": issue.get("label"), "severity": issue.get("severity"), "kind": "dummy"} if issue.get("code") != "healthy" else None,
        "satellite": {"ndvi": sat.get("latest_ndvi"), "date": sat.get("latest_date"), "change": sat.get("change"), "status": sat.get("status")} if sat else None,
        "layers": layer_rows,
        "layers_note": layers.get("note"),
        "photo": photo,
        "price": _msp(crop.get("name") or "", _expected(p)),
        "wildlife": wildlife.parcel_risk(crop.get("name") or "", p.get("zone") or "terrace", {**(p.get("wildlife") or {}), "kind": "dummy"}),
    }
    state.facts = facts

    asked = topics_asked(f"{state.query} {state.normalized_query or ''}") or ["all"]
    everything = "all" in asked
    parts: list[str] = []
    if everything or "owner" in asked:
        o = facts["owner"]
        parts.append(f"Owner: {o['name']} (patta {o['patta_no']}), field '{facts['field_name']}'. Owner names are dummy data.")
    if everything or "area" in asked:
        ha = facts["area_ha"] or 0
        parts.append(f"Area: {ha} ha ({ha * 2.471:.2f} acres).")
    if everything or "crop" in asked:
        c = facts["crop"]
        parts.append(f"Crop: {c['name']} ({c['variety']}), {str(c['stage']).split(' - ')[0]}, {c['days_after_planting']} days after planting (planted {c['planting_date']}). Crop records are dummy data.")
    if everything or "location" in asked:
        l = facts["location"]
        parts.append(f"Location: {l['lat']}, {l['lon']} ({facts['zone']} zone), elevation {l['elevation_m']} m.")
    if everything or "terrain" in asked:
        t = facts["terrain"]
        bits = [f"slope: {t.get('slope')}"]
        if t.get("direct_sun_hours") is not None:
            bits.append(f"direct sun about {t['direct_sun_hours']} h/day")
        if t.get("max_horizon_angle_deg") is not None:
            bits.append(f"terrain horizon up to {t['max_horizon_angle_deg']} degrees")
        parts.append("Terrain: " + ", ".join(bits) + ".")
    if everything or "soil" in asked:
        s = facts["soil"]
        parts.append(f"Soil (record, dummy): {s.get('texture')}, pH {s.get('ph')}; drainage {str(facts['terrain'].get('drainage_risk', '')).replace('_', ' ')}. "
                     "Modelled soil organic carbon is in the layers table.")
    if everything or "management" in asked:
        m = facts["management"]
        parts.append(f"Management (dummy): {m.get('irrigation_type')} irrigation, last irrigated {m.get('days_since_last_irrigation')} days ago, "
                     f"last fertilised {m.get('days_since_last_fertilizer')} days ago.")
    if everything or "layers" in asked:
        rows = [r for r in layer_rows if r["id"] != "tci"]
        ids = _asked_ids(state.query)
        want = rows if (everything or not ids) else ([r for r in rows if r["id"] in ids] or rows)
        shown = "; ".join(f"{r['name']} {r['value']}" for r in want)
        parts.append("Satellite layers at this parcel (real satellite data; ET is modelled; units and months are in the table below): " + shown + ".")
    if everything or "price" in asked:
        m = facts["price"]
        if m["has_msp"]:
            r = "; ".join(f"{x['crop']} Rs {x['msp_rs_per_quintal']}/quintal" for x in m["rows"])
            parts.append(f"Support price (MSP {m['year']}): {r}. " + (f"Indicative value of this parcel's expected crop at MSP: about Rs {m['indicative_value_rs']:,} ({m['indicative_basis']}). " if m.get("indicative_value_rs") else "") + m["note"])
        else:
            parts.append(m["note"])
    if everything or "wildlife" in asked:
        w = facts["wildlife"]
        order = {"high": 0, "medium": 1, "low": 2, "unlikely": 3}
        likely = [a for a in w["animals"] if order[a["level"]] <= 1]
        low = [a["animal"] for a in w["animals"] if a["level"] in ("low", "unlikely")]
        lines = [f"Wildlife risk for this {facts['zone']} {facts['crop']['name']} parcel (an indication from published studies and the zone, not a guarantee): "]
        lines.append("; ".join(f"{a['animal']} {a['level']}" for a in likely) + "." if likely else "no animal rates above low.")
        if low:
            lines.append("Low or unlikely: " + ", ".join(low) + ".")
        if likely:
            lines.append(f"For {likely[0]['animal']}: " + "; ".join(likely[0]["deterrents"][:3]).lower() + ".")
        if w.get("crop_standing"):
            lines.append(w["crop_standing"])
        parts.append(" ".join(lines))
    if everything or "photo" in asked:
        parts.append(photo["label"] + ("" if photo["url"] else ""))
    # the verifier adds the "TM-xx: crop, stage, days" opening when it is missing, so only prefix the id when that is already included
    prefix = f"{pid}: " if (everything or "crop" in asked) else ""
    state.raw_answer = prefix + " ".join(parts)
    state.recommendations = []
    state.limitations = (state.limitations or []) + ["Facts are read straight from the parcel record and the satellite layers; owner, crop and management values are dummy."]
    state.trace.append(TraceEntry(
        step="synthesize", tool_or_model="parcel_facts_lookup", why="Factual parcel question: answered exactly from the data, no language model",
        status="ok", latency_ms=(time.perf_counter() - t0) * 1000, est_cost_usd=0.0, input_summary=state.query[:80],
        output_summary="topics: " + ", ".join(asked)))
    return state


_LAYER_WORDS = {"ndvi": "ndvi", "ndmi": "ndmi", "ndwi": "ndwi", "evi": "evi", "savi": "savi", "ndre": "ndre", "rvi": "rvi", "rsm": "rsm",
                "radar": "rvi|rsm", "moisture": "rsm|ndmi", "evapotranspiration": "et", "water use": "et", "organic carbon": "soc",
                "soc": "soc", "land cover": "lulc", "landcover": "lulc", "lulc": "lulc", "greenness": "ndvi"}


def _asked_ids(q: str) -> set[str]:
    low = q.lower()
    out: set[str] = set()
    for w, ids in _LAYER_WORDS.items():
        if re.search(rf"\b{re.escape(w)}\b", low):
            out.update(ids.split("|"))
    return out
