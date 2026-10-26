"""
refphotos.py: reference photos of the problem a farmer asked about, so the answer can show what it looks like.

Chosen without any language model: from the photo matches of an uploaded picture, from a disease or pest named in the question, or from
the condition recorded on the parcel when the question is about a leaf or plant problem. They are reference photos from public datasets,
never a photo of the farmer's own field, and the card says so.
"""
from __future__ import annotations

import json
import re

from app import config
from app.schemas import PipelineState

_PROBLEM_WORDS = re.compile(r"\b(leaf|leaves|spot|spots|disease|pest|problem|yellow\w*|rust|blight|wilt|rot|mildew|symptom\w*|insect|worm|"
                            r"curl|mosaic|look\w*|photo|picture|what is wrong|how serious)\b", re.IGNORECASE)


_EXTRA = {"coconut_k_deficiency": {"url": "/images/coconut_k_deficiency_1.jpg", "condition": "Nutrient deficiency, yellowing fronds", "crop": "Coconut",
          "source": "Forest and Kim Starr, CC BY 2.0 (Wikimedia Commons)", "label": "Coconut · nutrient-deficiency yellowing (similar to potassium deficiency)"},
          "banana_k_deficiency": {"url": "/images/fertilizer/def_k.jpg", "condition": "Potassium deficiency (shown on cabbage, another crop)", "crop": "Banana",
                                  "source": "Wikimedia Commons, CC BY-SA 4.0 (K-deficient cabbage)", "label": "Potassium deficiency on another crop (cabbage): scorched, pale leaf edges. Banana shows yellowing and scorching on older leaf margins."},
          "cane_waterlogging_chlorosis": {"url": "/images/fertilizer/def_fe.jpg", "condition": "Iron chlorosis (shown on another plant)", "crop": "Sugarcane",
                                          "source": "baby-bear.org, CC BY 4.0 (Wikimedia Commons)", "label": "Iron chlorosis on another plant: new leaves turn pale yellow while veins stay green. Waterlogged cane can look like this."}}


def _items() -> list[dict]:
    try:
        return json.loads((config.DATA_DIR / "images" / "manifest.json").read_text(encoding="utf-8")).get("items", [])
    except Exception:  # noqa: BLE001
        return []


def _catalog() -> dict:
    try:
        return json.loads((config.DATA_DIR / "issue_catalog.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def reference_photos(state: PipelineState, limit: int = 3) -> list[dict]:
    items = [i for i in _items() if i.get("split") == "train" and i.get("condition_code") not in ("healthy", "field_scene")]
    q = f"{state.query} {state.normalized_query or ''}".lower()
    codes: list[str] = []

    for m in state.image_matches or []:                      # what the uploaded photo looked like
        c = m.get("condition_code")
        if c and c not in codes and c not in ("healthy", "field_scene"):
            codes.append(c)

    parcel_crop = ((state.parcel_context or {}).get("crop") or {}).get("name")
    asked_crop = (config.norm_crop(state.crop_hint).title() if state.crop_hint else "") or ""
    cat = _catalog()
    for code, meta in cat.items():                           # a disease or pest named in the question ("sigatoka", "red rot", "rust")
        label = str(meta.get("label", "")).lower()
        key = re.sub(r"\s*(leaf spot|leaf disease|disease|deficiency)$", "", label).strip() or label
        if code == "healthy" or len(key) < 4 or not re.search(r"\b" + re.escape(key), q):
            continue
        if parcel_crop and meta.get("crop") not in (parcel_crop, "any"):
            continue
        if asked_crop and meta.get("crop") not in (asked_crop, "any"):
            continue
        if not asked_crop and not parcel_crop and sum(1 for m2 in cat.values() if re.sub(r"\s*(leaf spot|leaf disease|disease|deficiency)$", "", str(m2.get("label", "")).lower()).strip() == key) > 1:
            continue                                         # "rust" or "leaf spot" with no crop named could be several crops: no guess
        if code not in codes:
            codes.append(code)

    issue = ((state.parcel_context or {}).get("observed_issue") or {}).get("code")
    if issue and issue != "healthy" and _PROBLEM_WORDS.search(q) and issue not in codes:
        codes.append(issue)                                  # the condition recorded on this parcel (dummy record)

    out: list[dict] = []
    compare = bool(re.search(r"differen|compare|comparison|versus|\bvs\b|distinguish|tell apart", q))
    per = 2 if compare and len(codes) > 1 else limit                    # a comparison question gets two photos of each condition, so the two can be seen side by side
    for code in codes[: 2 if compare else 1]:
        if code in _EXTRA:                                   # conditions the training sets have no photo for
            out.append(_EXTRA[code])
            continue                                   # one condition per answer keeps it readable
        pool = sorted((i for i in items if i["condition_code"] == code), key=lambda i: i["file"])
        step = max(1, len(pool) // per)
        for i in pool[::step][:per]:
            out.append({"url": f"/images/{i['file']}", "condition": i["condition"], "crop": i["crop"], "source": i.get("source"),
                        "label": f"{i['crop']} · {i['condition']}"})
    return out
