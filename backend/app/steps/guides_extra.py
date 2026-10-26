"""
guides_extra.py: variety guide, harvest and post-harvest card, and pesticide check. No language model, no AWS.

The variety and harvest cards quote the knowledge base (TNAU guides and the added web documents) passage by passage with the source named,
and add the parcel's own numbers (its variety, its growth-stage windows and the harvest dates they imply). The pesticide check compares a
named chemical with the banned and restricted lists in pesticides.py and points to the CIB&RC label-claim list for everything else.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from app import config, pesticides
from app.schemas import PipelineState

_CHUNKS: list[dict] = []


def _chunks() -> list[dict]:
    if not _CHUNKS:
        try:
            _CHUNKS.extend(json.loads(l) for l in open(config.CHUNKS_FILE, encoding="utf-8") if l.strip())
        except Exception:  # noqa: BLE001
            pass
    return _CHUNKS


def _crop(state: PipelineState) -> str | None:
    q = f"{state.query} {state.normalized_query or ''}".lower()
    for alias, c in config.CROP_ALIASES.items():
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", q):
            return c.capitalize()
    for c in config.CROPS:
        if re.search(rf"\b{c.lower()}\b", q):
            return c
    return ((state.parcel_context or {}).get("crop") or {}).get("name")


def _trim(text: str, limit: int = 460) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) <= limit:
        return t
    cut = t[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[: end + 1] if end > 200 else cut.rstrip() + "…")


def _pick(crop: str, topic: str, n: int = 3) -> list[dict]:
    pool = [c for c in _chunks() if c["crop"] == crop and topic in (c.get("topics") or [])[:2]]
    pool.sort(key=lambda c: ((c.get("topics") or []).index(topic), 0 if c.get("source_quality") == "A" else 1, -min(len(c["text"]), 700)))
    out, seen = [], set()
    for c in pool:
        key = c["text"][:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) == n:
            break
    return out


def _quote(c: dict) -> str:
    page = f", {c['page']}" if c.get("page") not in (None, "") else ""
    return f"{_trim(c['text'])} [{c['title']}{page}]"


_SRC = {"title": "TNAU Crop Production Guides 2020 and TNAU Agritech / Spices Board pages", "url": "https://agritech.tnau.ac.in/"}


# ── variety guide ────────────────────────────────────────────────────────────────────────────────────────────────────
VARIETY_RX = re.compile(r"variet(y|ies)|cultivars?|which\s+(seed|hybrid)|recommended\s+(seed|hybrid)|hybrids?\s+for|ரகம்|ரகங்கள்", re.IGNORECASE)
VARIETY_GUIDE_RX = re.compile(r"variety\s+guide|varieties\s+(of|for)\s+\w+\s*\??$|list\s+of\s+varieties|best\s+varieties", re.IGNORECASE)


def variety_card(state: PipelineState) -> dict | None:
    crop = _crop(state)
    if not crop:
        return None
    cs = _pick(crop, "variety_season")
    if not cs:
        return None
    p = state.parcel_context or {}
    pc = p.get("crop") or {}
    notes = ["Passages are quoted from the TNAU documents; names, durations and yields are as printed there. Ask your KVK which variety suits your soil, water and season."]
    if pc.get("name") == crop and pc.get("variety"):
        notes.insert(0, f"{p.get('parcel_id')} currently grows {pc['variety']} (parcel record, dummy data).")
    return {"id": "variety", "title": f"{crop} varieties: what the TNAU documents say", "kind": "knowledge", "steps": [_quote(c) for c in cs], "photos": [], "notes": notes, "warning": None,
            "videos": [], "contacts": [], "extra_sources": [], "asks": [{"label": f"Season to sow {crop}", "query": f"When is the best season to sow {crop}?"}], "source": _SRC}


# ── harvest and post-harvest ─────────────────────────────────────────────────────────────────────────────────────────
HARVEST_RX = re.compile(r"harvest|maturity|when\s+to\s+pick|post[\s-]?harvest|curing|ripening|picking|அறுவடை", re.IGNORECASE)
HARVEST_GUIDE_RX = re.compile(r"harvest\s+(guide|card|plan|time|window)|post[\s-]?harvest|when\s+will\s+(it|my\s+\w+)\s+be\s+ready", re.IGNORECASE)


def harvest_card(state: PipelineState) -> dict | None:
    crop = _crop(state)
    if not crop:
        return None
    lines: list[str] = []
    notes: list[str] = []
    p = state.parcel_context or {}
    pc = p.get("crop") or {}
    try:
        stages = json.loads((config.DATA_DIR / "crop_stages.json").read_text(encoding="utf-8")).get(crop) or []
    except Exception:  # noqa: BLE001
        stages = []
    if stages:
        last = stages[-1]
        first_late = next((s for s in stages if re.search(r"maturity|harvest|picking|opening", s["stage"], re.I)), last)
        lines.append(f"Harvest window in the project's stage table: day {first_late['from_day']} to day {last['to_day']} after planting ({first_late['stage']} to {last['stage']}).")
        if pc.get("name") == crop and pc.get("days_after_planting") is not None:
            plant = date.today() - timedelta(days=int(pc["days_after_planting"]))
            a, b = plant + timedelta(days=first_late["from_day"]), plant + timedelta(days=last["to_day"])
            left = first_late["from_day"] - int(pc["days_after_planting"])
            lines.append(f"{p.get('parcel_id')} was planted about {plant.strftime('%d %b %Y')}, so its harvest window is about {a.strftime('%d %b')} to {b.strftime('%d %b %Y')}"
                         + (f" ({left} days from now)." if left > 0 else " (it is in or past that window now)."))
    cs = _pick(crop, "harvest")
    lines += [_quote(c) for c in cs]
    if not lines:
        return None
    notes.append("After harvest: dry and clean the produce, grade it, and store it dry on raised planks away from walls; ask Cropsy 'how to store paddy seed' for the storage steps.")
    notes.append("Stage dates are an estimate from the planting date: confirm maturity in the field (and with your KVK) before cutting.")
    return {"id": "harvest", "title": f"{crop}: harvest and post-harvest", "kind": "knowledge", "steps": lines, "photos": [], "notes": notes, "warning": None, "videos": [], "contacts": [],
            "extra_sources": [], "asks": [{"label": "Store my produce", "query": "How to store grain and seed safely?"}], "source": _SRC}


# ── pesticide check ──────────────────────────────────────────────────────────────────────────────────────────────────
_CHECKW = r"(?:can\s+i\s+use|allowed|legal|illegal|banned|ban|registered|approved|permitted|safe\s+to\s+use)"
_CHEM = (r"(?:pesticide|insecticide|fungicide|herbicide|weedicide|chemical|endosulfan|monocrotophos|paraquat|glyphosate|carbofuran|phorate|methyl\s+parathion|lindane|ddt|"
         r"dimethoate|mancozeb|chlorpyrifos|chlorpyriphos|carbendazim|atrazine|imidacloprid|cypermethrin|profenofos|acephate|quinalphos)")
# "is endosulfan banned" and "can I use mancozeb": a check word near a chemical word, in either order (a bare "is" or "which fungicide" is not enough)
PEST_CHECK_RX = re.compile(rf"\b{_CHECKW}\b.{{0,40}}\b{_CHEM}\b|\b{_CHEM}\b.{{0,40}}\b{_CHECKW}\b|(?:banned|restricted)\s+(?:pesticide|chemical)|registered\s+(?:pesticide|product)|cibrc|label\s+claim", re.IGNORECASE)


def pesticide_card(state: PipelineState) -> dict | None:
    q = f"{state.query} {state.normalized_query or ''}"
    hits = pesticides.mentioned(q)
    lines = []
    for name, kind, note in hits:
        lines.append(f"{name.title()}: {kind.upper()}. {note[0].upper() + note[1:]}.")
    others = re.findall(r"\b(dimethoate|mancozeb|chlorpyrifos|chlorpyriphos|carbendazim|atrazine|imidacloprid|cypermethrin|profenofos|acephate|quinalphos|hexaconazole|propiconazole|tebuconazole)\b", q, re.I)
    for o in dict.fromkeys(x.lower() for x in others):
        lines.append(f"{o.title()}: not on the banned list Cropsy holds, but that does NOT mean it is registered for your crop and pest. Check its label claim on the CIB&RC list, and read the product label.")
    if not lines:
        lines.append("Cropsy keeps a short list of pesticides that are banned or restricted in India. Tell me the chemical name and I will check it against that list.")
    lines.append("To confirm that a product is registered for YOUR crop and pest, look it up in the CIB&RC 'label claim' list (Plant Protection, Quarantine and Storage Directorate) or ask your KVK or agriculture officer; buy only labelled, sealed packs.")
    return {"id": "pesticide_check", "title": "Pesticide check: banned, restricted, registered?", "kind": "knowledge", "steps": lines, "photos": ["em_sign"],
            "notes": ["The banned and restricted list here is short and may be out of date: it is a warning aid, not the legal register. TNAU documents quote chemicals as printed in 2020, so check the current status before buying.",
                      "Never mix pesticides or reuse empty containers."],
            "warning": ("Banned chemical named: do not use it." if any(k == "banned" for _, k, _ in hits) else None), "videos": [], "contacts": [], "extra_sources": [],
            "asks": [], "source": {"title": "CIB&RC / PPQS (Government of India) pesticide registration information", "url": pesticides.CIBRC_URL}}
