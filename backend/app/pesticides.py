"""
pesticides.py: a guard-rail list of pesticides that are banned or restricted in India, used to warn the farmer.

Only entries Cropsy is confident about are listed (the long-standing Government of India bans and the well-known use restrictions). It is NOT the
full CIBRC registration list: whether a product is registered for a given crop and pest is shown by that crop's "label claim" on the CIB&RC
website, so for any other chemical the card says so and points there. A draft 2020 order proposing more bans was not finalised, so those
products are not listed as banned here.
"""
from __future__ import annotations

import re

BANNED = {
    "endosulfan": "banned (Supreme Court order and ban notification, 2011)",
    "lindane": "banned for agricultural use",
    "ddt": "banned for agricultural use (only restricted public-health use remains)",
    "aldrin": "banned", "dieldrin": "banned", "endrin": "banned", "heptachlor": "banned", "chlordane": "banned", "toxaphene": "banned", "toxafene": "banned",
    "benzene hexachloride": "banned", "bhc": "banned",
    "ethyl parathion": "banned", "nitrofen": "banned", "pentachlorophenol": "banned", "pentachloro nitrobenzene": "banned", "tetradifon": "banned",
    "maleic hydrazide": "banned", "menazon": "banned", "aldicarb": "banned", "calcium cyanide": "banned (restricted fumigant use only)",
    "dibromochloropropane": "banned", "copper acetoarsenite": "banned", "sodium methane arsonate": "banned",
    "phenyl mercury acetate": "banned", "ethyl mercury chloride": "banned", "paraquat dimethyl sulphate": "banned",
    "carbon tetrachloride": "banned",
    # Insecticides (Prohibition) Order 2023 (Gazette notification dated 29 September 2023): see REGULATORY below. Status taken from secondary reports of the order; confirm with CIB&RC / your KVK.
    "dicofol": "banned (Insecticides (Prohibition) Order 2023)",
    "dinocap": "banned (Insecticides (Prohibition) Order 2023)",
    "methomyl": "banned (Insecticides (Prohibition) Order 2023)",
    "monocrotophos": "banned (Insecticides (Prohibition) Order 2023: the 36% SL formulation could be sold or used only to clear existing stock during a one-year window; earlier banned on vegetables)",
}
RESTRICTED = {
    "methyl parathion": "banned on fruits and vegetables; restricted otherwise: ask the KVK",
    "paraquat": "restricted: a highly toxic weedkiller, allowed only under strict conditions and a frequent cause of poisoning: ask the KVK first",
    "phorate": "highly toxic granular insecticide, restricted in use: ask the KVK",
    "carbofuran": "highly toxic. The October 2023 order restricts all formulations except the 3% encapsulated granule (CG); check the label claim for your crop and ask the KVK",
    "glyphosate": "use was restricted in 2022 to licensed pest-control operators: check the current notice and ask the KVK before using it",
}
CIBRC_URL = "https://ppqs.gov.in/"
# What the status notes above rest on. Checked 2026-10-16 from secondary reports (PAN India, 7 Oct 2023, quoting the Gazette order of 29 Sep 2023; APEDA's Farmer Connect list was not
# reachable; the PIB release returned HTTP 403). It is NOT a legal opinion and it has not been confirmed with CIB&RC. A qualified reviewer must confirm each entry.
REGULATORY = {
    "monocrotophos": {"status": "banned (use) per the 2023 order; the 36% SL window for existing stock was one year", "checked": "2026-10-16", "confirmed_with_cibrc": False,
                      "basis": "Insecticides (Prohibition) Order 2023, Gazette notification 29 Sep 2023: dicofol, dinocap, methomyl and monocrotophos; monocrotophos 36% SL 'only for clearance of existing stock'",
                      "sources": ["https://pan-india.org/india-bans-four-highly-hazardous-pesticides-pan-india-welcomes-this-step/"],
                      "caution": "TNAU's 2020 guide still lists it for cotton and other crops: that text predates the order"},
    "carbofuran": {"status": "restricted: all formulations except the 3% encapsulated granule (CG)", "checked": "2026-10-16", "confirmed_with_cibrc": False,
                   "basis": "October 2023 order as reported (S.O. 4294(E) is cited by one secondary source)", "sources": ["https://pan-india.org/india-bans-four-highly-hazardous-pesticides-pan-india-welcomes-this-step/"],
                   "caution": "highly toxic; use only where the label claim allows it for the crop and pest"},
    "paraquat": {"status": "paraquat dimethyl sulphate is on the banned list; paraquat dichloride is restricted", "checked": "2026-10-16", "confirmed_with_cibrc": False,
                 "basis": "the Odisha government's 'List of pesticides banned in India' (27 items for manufacture, import and use) names paraquat dimethyl sulphate",
                 "sources": ["https://odishaagrilicense.nic.in/public/actsRules/LIST%20OF%20BANNED%20PESTICIDES.pdf"], "caution": "frequent cause of poisoning; refer to the KVK first"},
}
_NAMES = sorted({*BANNED, *RESTRICTED}, key=len, reverse=True)
_RX = re.compile(r"(?<![a-z])(" + "|".join(re.escape(n) for n in _NAMES) + r")(?![a-z])", re.IGNORECASE)


# Tamil transliterations (written from general knowledge; a spelling not listed here will not be caught, so the Latin-script check stays the main guard)
TAMIL_NAMES = {"எண்டோசல்பான்": "endosulfan", "என்டோசல்பான்": "endosulfan", "எண்டோசல்ஃபான்": "endosulfan", "மோனோக்ரோடோபாஸ்": "monocrotophos", "மோனோகுரோட்டோபாஸ்": "monocrotophos",
               "லிண்டேன்": "lindane", "பாராக்வாட்": "paraquat", "பாரகுவாட்": "paraquat", "கார்போபியூரான்": "carbofuran", "கார்போபுரான்": "carbofuran", "பாரத்தியான்": "methyl parathion",
               "ஃபோரேட்": "phorate", "கிளைபோசேட்": "glyphosate", "டிடிடி": "ddt"}


def mentioned(text: str) -> list[tuple[str, str, str]]:
    """Banned or restricted chemicals named in a text: [(name, 'banned'|'restricted', note)]."""
    out, seen = [], set()
    text = text or ""
    for ta, en in TAMIL_NAMES.items():
        if ta in text:
            text += f" {en} "
    for m in _RX.finditer(text):
        n = m.group(1).lower()
        if n in seen:
            continue
        seen.add(n)
        if n in BANNED:
            out.append((n, "banned", BANNED[n]))
        else:
            out.append((n, "restricted", RESTRICTED[n]))
    return out
