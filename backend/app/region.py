"""region.py: where the farmer is, and which region a piece of knowledge applies to.

Why: the same crop needs different sowing dates, varieties, fertilizer doses and pest control in different places. Every source in the knowledge base is Tamil Nadu (TNAU) except one national
turmeric PDF, so a recommendation must say where it applies, and a question from elsewhere must not be answered as if it were Tamil Nadu advice.

A region is {"country", "state", "district", "zone", "source"}; any part may be None. 'source' says how we know: question (the farmer wrote it), profile (the farmer saved it, with consent),
parcel (the selected parcel is in Then Malai, Tenkasi, Tamil Nadu) or unknown. Nothing here is stored on the server.
Chunks carry an optional "region" field; a chunk without one gets the default of its document (see chunk_region)."""
from __future__ import annotations

import re
from typing import Optional

TN = "Tamil Nadu"
STATES = {
    "Andhra Pradesh": ["andhra pradesh", "andhra", "ఆంధ్ర"], "Arunachal Pradesh": ["arunachal"], "Assam": ["assam"], "Bihar": ["bihar"], "Chhattisgarh": ["chhattisgarh"], "Goa": ["goa"],
    "Gujarat": ["gujarat"], "Haryana": ["haryana"], "Himachal Pradesh": ["himachal"], "Jharkhand": ["jharkhand"], "Karnataka": ["karnataka", "ಕರ್ನಾಟಕ"], "Kerala": ["kerala", "கேரளா", "கேரளம்"],
    "Madhya Pradesh": ["madhya pradesh"], "Maharashtra": ["maharashtra"], "Manipur": ["manipur"], "Meghalaya": ["meghalaya"], "Mizoram": ["mizoram"], "Nagaland": ["nagaland"],
    "Odisha": ["odisha", "orissa"], "Punjab": ["punjab"], "Rajasthan": ["rajasthan"], "Sikkim": ["sikkim"], "Tamil Nadu": ["tamil nadu", "tamilnadu", "தமிழ்நாடு", "தமிழகம்"],
    "Telangana": ["telangana"], "Tripura": ["tripura"], "Uttar Pradesh": ["uttar pradesh"], "Uttarakhand": ["uttarakhand"], "West Bengal": ["west bengal"],
    "Delhi": ["delhi"], "Jammu and Kashmir": ["jammu", "kashmir"], "Puducherry": ["puducherry", "pondicherry", "புதுச்சேரி"], "Ladakh": ["ladakh"],
}
COUNTRIES = {"Sri Lanka": ["sri lanka", "srilanka", "இலங்கை"], "Bangladesh": ["bangladesh"], "Nepal": ["nepal"], "Pakistan": ["pakistan"], "India": ["india", "இந்தியா"]}
# Tamil Nadu districts, each with the agro-climatic zone the TNAU guides use (zone names as printed in the guides' variety tables)
DISTRICTS = {
    "Tenkasi": "Southern", "Tirunelveli": "Southern", "Thoothukudi": "Southern", "Kanyakumari": "High Rainfall", "Madurai": "Southern", "Theni": "Southern", "Dindigul": "Southern", "Virudhunagar": "Southern",
    "Ramanathapuram": "Southern", "Sivaganga": "Southern", "Pudukkottai": "Southern", "Coimbatore": "Western", "Tiruppur": "Western", "Erode": "Western", "Karur": "Western", "Nilgiris": "Hilly",
    "Salem": "North Western", "Namakkal": "North Western", "Dharmapuri": "North Western", "Krishnagiri": "North Western", "Vellore": "North Eastern", "Tiruvannamalai": "North Eastern",
    "Cuddalore": "North Eastern", "Villupuram": "North Eastern", "Kallakurichi": "North Eastern", "Chennai": "North Eastern", "Tiruvallur": "North Eastern", "Kancheepuram": "North Eastern",
    "Chengalpattu": "North Eastern", "Ranipet": "North Eastern", "Tirupathur": "North Eastern", "Thanjavur": "Cauvery Delta", "Tiruvarur": "Cauvery Delta", "Nagapattinam": "Cauvery Delta",
    "Mayiladuthurai": "Cauvery Delta", "Tiruchirappalli": "Cauvery Delta", "Ariyalur": "Cauvery Delta", "Perambalur": "Cauvery Delta",
}
DISTRICT_ALIASES = {"Nellai": "Tirunelveli", "Trichy": "Tiruchirappalli", "Tuticorin": "Thoothukudi", "Kanchipuram": "Kancheepuram", "Thiruvallur": "Tiruvallur", "Coimbatore": "Coimbatore", "Ooty": "Nilgiris"}

# questions whose answer depends on where the farmer is
_SENSITIVE = re.compile(
    r"sowing\s+(time|season|date)|when\s+(to|should)\s+(i\s+)?(sow|plant|transplant)|season|variet(y|ies)|hybrid|seed\s+rate|dose|how\s+much|fertili[sz]er|urea|\bdap\b|spray|pesticide|fungicide|insecticide|"
    r"irrigation\s+(schedule|interval)|spacing|ஏற்ற\s*பட்டம்|பட்டம்|எவ்வளவு|உரம்|ரகம்", re.IGNORECASE)


def _find(text: str, table: dict[str, list[str]]) -> Optional[str]:
    low = (text or "").lower()
    best, at = None, 10 ** 9
    for name, words in table.items():
        for w in words:
            m = re.search(r"(?<![a-z])" + re.escape(w.lower()) + r"(?![a-z])", low) if w.isascii() else (low.find(w.lower()) >= 0 and re.search(re.escape(w.lower()), low))
            if m and (m.start() if hasattr(m, "start") else 0) < at:
                best, at = name, (m.start() if hasattr(m, "start") else 0)
    return best


def unknown() -> dict:
    return {"country": None, "state": None, "district": None, "zone": None, "source": "unknown"}


def detect(text: str) -> dict:
    """Region named in the farmer's own words. A district implies its state and zone; a state implies India."""
    out = unknown()
    state = _find(text, STATES)
    country = _find(text, {k: v for k, v in COUNTRIES.items() if k != "India"})
    low = (text or "").lower()
    district = None
    for d in DISTRICTS:
        if re.search(r"(?<![a-z])" + d.lower() + r"(?![a-z])", low):
            district = d
            break
    if not district:
        for alias, d in DISTRICT_ALIASES.items():
            if re.search(r"(?<![a-z])" + alias.lower() + r"(?![a-z])", low):
                district = d
                break
    if district:
        out.update(country="India", state=TN, district=district, zone=DISTRICTS[district], source="question")
    elif state:
        out.update(country="India", state=state, source="question")
    elif country:
        out.update(country=country, source="question")
    elif _find(text, {"India": COUNTRIES["India"]}):
        out.update(country="India", source="question")
    return out


def from_parcel(parcel: Optional[dict]) -> Optional[dict]:
    """The demo village is Then Malai, Tenkasi district, Tamil Nadu."""
    if not parcel:
        return None
    return {"country": "India", "state": TN, "district": "Tenkasi", "zone": DISTRICTS["Tenkasi"], "source": "parcel"}


def resolve(query: str, profile: Optional[dict] = None, parcel: Optional[dict] = None) -> dict:
    """The farmer's words win; then a saved profile; then the selected parcel; otherwise unknown."""
    r = detect(query)
    if r["source"] != "unknown":
        return r
    if profile and any(profile.get(k) for k in ("country", "state", "district")):
        p = {**unknown(), **{k: profile.get(k) for k in ("country", "state", "district", "zone")}, "source": "profile"}
        if p["district"] and not p["state"]:
            p["state"], p["country"] = TN if p["district"] in DISTRICTS else None, "India"
        if p["district"] in DISTRICTS and not p["zone"]:
            p["zone"] = DISTRICTS[p["district"]]
        return p
    return from_parcel(parcel) or unknown()


def chunk_region(chunk: dict) -> dict:
    """The region a chunk applies to: its own 'region' field if present, otherwise the default of its document."""
    r = chunk.get("region")
    if isinstance(r, dict) and (r.get("state") or r.get("country")):
        return r
    if str(chunk.get("document_id", "")).startswith("PDF_SPICES"):
        return {"country": "India", "state": None, "applies_to": "all India (national publication)"}
    return {"country": "India", "state": TN, "applies_to": "Tamil Nadu"}


def match(query_region: dict, chunk: dict) -> str:
    """'zone' | 'state' | 'country' | 'mismatch' | 'unknown'. A national chunk (no state) matches any state in India at 'country' level."""
    qs, qc = query_region.get("state"), query_region.get("country")
    if not qs and not qc:
        return "unknown"
    cr = chunk_region(chunk)
    if qc and cr.get("country") and qc != cr["country"]:
        return "mismatch"
    if qs and cr.get("state"):
        if qs != cr["state"]:
            return "mismatch"
        qz, cz = query_region.get("zone"), cr.get("zone")
        return "zone" if (qz and cz and qz == cz) else "state"
    return "country"


def is_sensitive(query: str) -> bool:
    return bool(_SENSITIVE.search(query or ""))


def kb_states() -> set[str]:
    """States for which the knowledge base holds a regional source (today only Tamil Nadu)."""
    return {TN}


def note_for(query: str, region: dict) -> Optional[str]:
    """A short, honest line about where the advice applies, or None when nothing needs saying."""
    st = region.get("state")
    if region["source"] == "unknown":
        if is_sensitive(query):
            return "Advice is from Tamil Nadu (TNAU) sources. If you farm elsewhere, set your region: sowing time, varieties and doses differ by place."
        return None
    if st and st not in kb_states():
        return f"Cropsy's checked advice is for Tamil Nadu. For {st} this is general guidance only: confirm with your state agricultural university or KVK."
    if region.get("country") and region["country"] != "India":
        return f"Cropsy's verified recommendations are for Tamil Nadu, India. For {region['country']} this is general guidance only."
    return None
