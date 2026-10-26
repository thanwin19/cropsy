"""quantities.py: read "number + unit + basis" claims from text so an answer can be checked against its evidence in context.

A figure is only right with its context: "3.75 kg" is a nursery rate per 7.5 cents, "12.5 kg per hectare" is a field rate for shoot-fly areas. An answer that
joins them into "3.75 to 12.5 kg per hectare" uses numbers that are all in the source but means something the source never says. This module extracts
(value, unit, basis) triples from both the answer and the evidence so verify.py can compare them. It does not judge agronomy; it only checks that a
quantity keeps the basis (per hectare, per acre, per cent, per litre, per plant ...) it has in the source.
"""
from __future__ import annotations

import re

# Tamil units and words -> the English tokens used below (the answer may be written in Tamil; the digits stay Latin).
_TAMIL = [
    ("ஹெக்டேருக்கு", " per ha "), ("ஹெக்டருக்கு", " per ha "), ("எக்டருக்கு", " per ha "), ("ஹெக்டேர்", " ha "), ("எக்டர்", " ha "),
    ("கிலோ", " kg "), ("கிராம்", " g "), ("மில்லி", " ml "), ("மி.லி", " ml "), ("லிட்டர்", " l "), ("சென்ட்", " cent "), ("செண்ட்", " cent "),
    ("ஏக்கருக்கு", " per acre "), ("ஏக்கர்", " acre "), ("டன்", " t "),
]

_NUM = r"(\d+(?:\.\d+)?)"
_UNIT = r"(kg|g|mg|ml|l|lit|litres?|liters?|t|tonnes?|tons?|q|quintals?|cm|metres?|meters?)"
_BASIS = r"(ha|hectares?|acres?|cents?|plants?|palms?|trees?|litres?|liters?|lit|l|m2|sq\s*m|hill|pit|seedlings?|nursery)"
_QTY = re.compile(
    rf"(?<![\w.]){_NUM}\s*{_UNIT}\b(?:\s+of\s+(?:seeds?|grains?))?"
    rf"(?:\s*(?:/|per|in|for|@)\s*(?:the\s*|a\s*|one\s*|every\s*)?(?:{_NUM}\s*)?{_BASIS}\b)?",
    re.IGNORECASE,
)
_FAMILY = {"ha": "ha", "hectare": "ha", "hectares": "ha", "acre": "acre", "acres": "acre", "cent": "cent", "cents": "cent",
           "plant": "plant", "plants": "plant", "palm": "palm", "palms": "palm", "tree": "tree", "trees": "tree",
           "l": "l", "lit": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l", "m2": "m2", "sq m": "m2", "hill": "hill", "pit": "pit",
           "seedling": "seedling", "seedlings": "seedling", "nursery": "nursery"}
_UNIT_FAMILY = {"litre": "l", "litres": "l", "liter": "l", "liters": "l", "lit": "l", "tonne": "t", "tonnes": "t", "ton": "t", "tons": "t",
                "quintal": "q", "quintals": "q"}


def _prep(text: str) -> str:
    t = (text or "").replace(" ", " ").replace("**", "")
    for ta, en in _TAMIL:
        t = t.replace(ta, en)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:to|-|–|முதல்)\s*(\d+(?:\.\d+)?)\s*(kg|g|ml|l|cm|t)\b", r"\1 \3 to \2 \3", t)     # "12 to 15 kg" is two quantities in kg
    return t


def quantities(text: str) -> list[tuple[str, str, str | None, int]]:
    """[(value, unit, basis or None, position)]. A quantity written without a basis in a range ('3.75 kg to 12.5 kg per ha') takes the basis of the range's end."""
    t = _prep(text)
    found = []
    for m in _QTY.finditer(t):
        unit = m.group(2).lower()
        unit = _UNIT_FAMILY.get(unit, unit)
        basis = m.group(4).lower() if m.group(4) else None
        basis = _FAMILY.get(basis, basis) if basis else None
        value = m.group(1)
        found.append([value, unit, basis, m.start(), m.end()])
    for q in found:                                                      # Tamil word order puts the basis first: "per hectare about 3.75 kg"
        if q[2] is None:
            m = re.search(r"per\s+(ha|acre|cent|l)\s+(?:\S+\s+){0,2}$", t[max(0, q[3] - 28):q[3]])
            if m:
                q[2] = m.group(1)
    for i, q in enumerate(found[:-1]):                                   # "3.75 kg to 12.5 kg per hectare": the first figure is read with the same basis the writer gives the range
        if q[2] is None and found[i + 1][2]:
            between = t[q[4]:found[i + 1][3]].strip().lower()
            if between in ("to", "-", "–", "and", "or", "up to", "upto", "to about", "—", "முதல்"):
                q[2] = found[i + 1][2]
    return [(v, u, b, p) for v, u, b, p, _e in found]


def basis_mismatches(answer: str, evidence_texts: list[str]) -> list[str]:
    """Quantities in the answer that carry a basis (per ha, per cent, ...) which the evidence does not give that same figure. Returns readable descriptions.

    A figure the evidence lacks entirely is not reported here (V2 deals with doses); a figure the evidence gives with NO basis nearby is not reported either,
    because table cells often lose their column header in extraction and that would flag correct answers."""
    ev = [quantities(t) for t in evidence_texts]
    bad = []
    seen = set()
    for v, u, b, _p in quantities(answer):
        if b is None or (v, u, b) in seen:
            continue
        seen.add((v, u, b))
        same_figure = [q for qs in ev for q in qs if q[0] == v and q[1] == u]
        if not same_figure:
            continue
        if any(q[2] == b or q[2] is None for q in same_figure):
            continue
        bad.append(f"{v} {u} per {b}: the source gives {v} {u} per {', '.join(sorted({q[2] for q in same_figure if q[2]}))}")
    return bad


def numbers(text: str) -> set[str]:
    """Every figure written with a unit in the text (used to find which evidence passage supports an answer)."""
    return {f"{v} {u}" for v, u, _b, _p in quantities(text)}


# --- figures that appear nowhere in the evidence --------------------------------------------------------------------------------------
_TO_BASE = {"metre": 100.0, "metres": 100.0, "meter": 100.0, "meters": 100.0, "cm": 1.0, "%": 1.0, "kg": 1.0, "g": 0.001, "mg": 0.000001, "t": 1000.0, "q": 100.0, "l": 1.0, "ml": 0.001}
_ACRE_PER_HA = 0.4047


def _base(v: str, u: str) -> tuple[str, float] | None:
    k = "mass" if u in ("kg", "g", "mg", "t", "q") else "vol" if u in ("l", "ml") else "len" if u in ("cm", "metre", "metres", "meter", "meters") else "pct" if u == "%" else None
    if not k or u not in _TO_BASE:
        return None
    return k, float(v) * _TO_BASE[u]


_SPACING = re.compile(r"(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*cm", re.IGNORECASE)
_PCT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:%|per\s*cent\b)", re.IGNORECASE)


def _figures(text: str) -> list[tuple[str, str]]:
    t = _prep(text)
    out = [(v, u) for v, u, _b, _p in quantities(t)]
    for m in _SPACING.finditer(t):
        out += [(m.group(1), "cm"), (m.group(2), "cm")]
    out += [(m.group(1), "%") for m in _PCT.finditer(t)]
    return out


def unsupported(answer: str, evidence_texts: list[str]) -> list[str]:
    """Quantities (value + mass or volume unit) in the answer that no evidence passage contains, allowing g<->kg, ml<->l and per-acre<->per-hectare
    conversions. A figure made up, or misread from another row ('increase to 10 kg' where the source says 12.5 kg), shows up here."""
    ev = set()
    for t in evidence_texts:
        for v, u in _figures(t):
            b = _base(v, u)
            if b:
                ev.add(b)
    out, seen = [], set()
    t_ans = _prep(answer)
    ans = [(v, u, b) for v, u, b, _p in quantities(t_ans)] + [(v, "cm", None) for m in _SPACING.finditer(t_ans) for v in m.groups()] + [(m.group(1), "%", None) for m in _PCT.finditer(t_ans)]
    for v, u, basis in ans:
        key = (v, u)
        base = _base(v, u)
        if not base or key in seen:
            continue
        seen.add(key)
        ok = False
        for k, x in ev:
            if k != base[0]:
                continue
            for factor in ((1.0, _ACRE_PER_HA, 1 / _ACRE_PER_HA) if basis == "acre" else (1.0,)):                 # per-acre figures may be converted from per-hectare ones; a coincidence with another figure is not support
                if abs(base[1] - x * factor) <= max(1e-9, 0.03 * x * factor):
                    ok = True
                    break
            if ok:
                break
        if not ok:
            out.append(f"{v} {u}")
    return out


_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_DATE = re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)\b|\b(?:{_MONTHS})\b", re.IGNORECASE)


def support_score(claim_text: str, passage: str) -> int:
    """How much of what the answer claims this passage proves: a shared quantity (value + unit [+ basis]) counts 3, a shared date or month 2. Bare small numbers count nothing."""
    cq = {(v, u) for v, u in _figures(claim_text)}
    pq = {(v, u) for v, u in _figures(passage)}
    cd = {m.lower() for m in _DATE.findall(_prep(claim_text))}
    pd = {m.lower() for m in _DATE.findall(_prep(passage))}
    return 3 * len(cq & pq) + 2 * len(cd & pd)


# --- a figure must be the right KIND of figure ----------------------------------------------------------------------------------------
# "The seed rate for cowpea is 2 kg/ha": the 2 kg/ha in the guide is phosphobacteria, not seed. The figure exists, the basis is right, but its purpose is
# different. For the purposes that farmers act on directly (seed rate, spacing, seed treatment) the passage must show the figure next to words of that purpose.
_PURPOSES = {
    "seed rate": (r"seed rate|seed requirement|seeds? per (ha|hectare|acre)|rate of seeds?|விதை அளவு|விதை வீதம்|விதை தேவை",
                  r"seed rate|seed requirement|rate of seeds?|\d+\s*(kg|g)\s*(of\s*)?seeds?\s*(/|per|for|in)\s*(ha|hectare|acre|cent|m2)|(kg|g)\s*(/|per)\s*(ha|hectare|acre)\s*of seeds?|sow\w*[^.]{0,40}\d+\s*kg"),
    "spacing": (r"spacing|between rows|between plants|இடைவெளி",
                r"spacing|\d+\s*(x|×)\s*\d+|apart|between (the )?(rows|plants|lines|hills)"),
    "seed treatment": (r"seed treatment|treat the seeds?|விதை நேர்த்தி",
                       r"seed treatment|treat\w* (the )?seeds?|(g|ml|kg) ?(/|per) ?(kg|l) of seeds?|(g|ml) ?/ ?kg seeds?|per kg of seed|soak"),
}


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", _prep(text)) if s.strip()]


def purpose_mismatches(answer: str, question: str, evidence_texts: list[str]) -> list[str]:
    """Figures the answer gives as a seed rate / spacing / seed treatment that the evidence shows for a different purpose. Checked per sentence: a sentence that
    names the purpose, or the first figure-bearing sentence when the question asks for that purpose."""
    ev = [_prep(t) for t in evidence_texts]
    bad: list[str] = []
    first_done = False
    for sent in _sentences(answer):
        figs = [(v, u) for v, u in _figures(sent) if u in ("kg", "g", "ml", "l", "cm", "t", "q", "metre", "metres", "meter", "meters")]
        if not figs:
            continue
        asked_first = not first_done
        first_done = True
        for name, (sent_rx, ev_rx) in _PURPOSES.items():
            in_sent = re.search(sent_rx, sent, re.IGNORECASE)
            in_q = re.search(sent_rx, question or "", re.IGNORECASE) and asked_first
            if not (in_sent or in_q):
                continue
            for v, u in figs:
                found_any, ok = False, False
                for t in ev:
                    for m in re.finditer(rf"(?<![\w.]){re.escape(v)}\s*{u}\b|(?<![\w.]){re.escape(v)}\s*(?:x|×)", t, re.IGNORECASE):
                        found_any = True
                        window = t[max(0, m.start() - 120):m.end() + 120]
                        if re.search(ev_rx, window, re.IGNORECASE):
                            ok = True
                            break
                    if ok:
                        break
                if found_any and not ok:
                    bad.append(f"{v} {u} is not given as the {name} in the evidence")
    return list(dict.fromkeys(bad))


# --- a dose belongs to ONE product ------------------------------------------------------------------------------------------------------
# "Chlorantraniliprole 18.5% SC 100 ml/ha" is wrong when the guide says 150 ml/ha for it and 100 ml/ha for flubendiamide: the number exists in the guide, but it is flubendiamide's.
# Every dose is tied to the product written just before it ("owner"), in the answer and in the evidence, and an answer pairing is rejected when the evidence gives that
# product a different dose.
_FORMULATION = re.compile(r"\b\d+(?:\.\d+)?\s*%?\s*(?:EC|SC|WP|WG|SL|SP|G|GR|DP|WS|FS|CG|ZC|OD|SE|EW|CS|DF|WDG|AS)\b\.?|@|\bat\b|\bof\b|\ba\.i\.?", re.IGNORECASE)
_DOSE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(kg|g|ml|l|lit|litres?|liters?)\b(?:\s*(?:/|per)\s*(ha|hectare|acre|l|lit|litre|litres|liter|kg|palm|plant|tree|cent|m2|pit)\b)?", re.IGNORECASE)      # the basis may be written once for a list ("carbendazim @ 500 g or IBP @ 500 ml/ha")
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]{4,}")
_NOT_PRODUCT = {"spray", "apply", "dose", "doses", "insecticide", "insecticides", "fungicide", "fungicides", "following", "recommended", "treat", "seeds", "seed", "weekly", "water", "litre",
                "hectare", "foliar", "control", "pests", "pest", "disease", "diseases", "ml/ha", "per", "plus", "mixed", "alternatively", "either", "should", "about", "using", "followed",
                "repeat", "after", "before", "days", "first", "second", "formulation", "granules", "powder", "liquid", "soil", "crop", "field", "treatment", "management", "strategies"}


def _unit_key(v: str, u: str) -> tuple[float, str]:
    """The dose in grams or millilitres, so 625 g and 0.625 kg, 3750 ml and 3.75 l compare equal."""
    u = u.lower()
    u = {"lit": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l"}.get(u, u)
    x = float(v)
    if u == "kg":
        x, u = x * 1000, "g"
    elif u == "l":
        x, u = x * 1000, "ml"
    return round(x, 3), u


def dose_owners(text: str) -> list[tuple[str, tuple[float, str]]]:
    """[(product word, (value, unit))]: each dose with the product named just before it in the same clause."""
    t = _prep(text)
    t = t.replace("*", " ")
    out = []
    last_end = 0
    for m in _DOSE.finditer(t):
        seg = t[last_end:m.start()]
        last_end = m.end()
        seg = re.split(r"(?<!\d)\.|\.(?!\d)|;|\n|\bor\b|\band\b|,", seg)[-1]
        seg = _FORMULATION.sub(" ", seg)
        words = [w.lower() for w in _WORD.findall(seg) if w.lower() not in _NOT_PRODUCT]
        if words:
            out.append((words[-1], _unit_key(m.group(1), m.group(2))))
    return out


def product_dose_mismatches(answer: str, evidence_texts: list[str]) -> list[str]:
    """Answer pairings (product, dose) that the evidence contradicts: the evidence gives that product other doses and not this one."""
    ev: dict[str, set] = {}
    for t in evidence_texts:
        for owner, key in dose_owners(t):
            ev.setdefault(owner, set()).add(key)
    bad = []
    for owner, key in dose_owners(answer):
        have = ev.get(owner)
        if have and key not in have:
            bad.append(f"{owner} {key[0]:g} {key[1]}")
    return list(dict.fromkeys(bad))


def ambiguous_products(answer: str, evidence_texts: list[str]) -> list[str]:
    """Products in the answer for which the evidence itself gives more than one dose (the guide lists them per pest or per stage): the answer should say which applies."""
    ev: dict[str, set] = {}
    for t in evidence_texts:
        for owner, key in dose_owners(t):
            ev.setdefault(owner, set()).add(key)
    return sorted({o for o, _k in dose_owners(answer) if len(ev.get(o, ())) > 1})
