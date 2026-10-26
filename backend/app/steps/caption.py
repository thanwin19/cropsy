"""
caption.py: Caption, Judge, then Diagnose (the CPJ idea) for crop photos.

1  CAPTION   Nova Lite looks at the photo and writes a structured description of what is visible. It is told NOT to name the crop,
             the disease or the cause, so no early guess can colour the description.
2  JUDGE     Rules plus Nova Micro check the caption: every field present, severity given, uncertainty stated, and no crop or disease
             name leaked in. Fields that fail are rewritten by the judge; if the caption still fails, Nova Lite describes the photo once more.
3  CHECK     (after retrieval) Nova Micro scores each condition of the crop against the caption. When the top score names the same condition as
             the nearest reference photos, the report says the description supports it. When it does not, it is shown as "not confirmed"
             only: on 20 held-out photos the reference match was right 19/20 and the caption-only choice 10/20, so the caption is explanation, not a veto.

The final answer model never sees the image: it reads this caption, the reference-photo matches and the TNAU passages, so the
description is the traceable evidence behind every photo answer. If any step cannot run, the older one-shot vision step is used.
Set CROPSY_CPJ=off to switch the whole thing off.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

from app import config
from app.models import bedrock
from app.schemas import PipelineState, TraceEntry

log = logging.getLogger(__name__)

FIELDS = ["plant_part", "lesion_colour", "lesion_shape", "margin_and_halo", "distribution", "texture_or_growth", "insects_or_damage", "severity_percent", "image_quality", "uncertainty"]
LABELS = {"plant_part": "Affected part", "lesion_colour": "Lesion colour", "lesion_shape": "Shape", "margin_and_halo": "Margin", "distribution": "Distribution",
          "texture_or_growth": "Surface", "insects_or_damage": "Insects or damage", "severity_percent": "Severity", "image_quality": "Photo quality", "uncertainty": "Uncertainty"}
QUALITY = {"good", "dark", "blurry", "too_far", "partial"}

CAPTION_PROMPT = """You are describing a crop photograph for a plant-pathology expert who cannot see it.
Describe ONLY what is visible. Do NOT name the crop, any disease, any pest or any cause. Use plain words for colours, shapes and positions.
Return JSON only, with exactly these keys:
{
 "plant_part": "leaf | stem | fruit | root | whole plant | field | other",
 "lesion_colour": "centre and edge colours of any spots or patches",
 "lesion_shape": "round, oval, diamond, streak, irregular, ...",
 "margin_and_halo": "edge colour and any yellow ring",
 "distribution": "where on the leaf or plant, and how it spreads",
 "texture_or_growth": "powdery, fuzzy, wet, dry, rolled, holes, ... or none",
 "insects_or_damage": "insects, webbing, chewing or none visible",
 "severity_percent": "estimated share of the visible area affected, as a range such as 10-20",
 "image_quality": "good | dark | blurry | too_far | partial",
 "uncertainty": ["what you cannot tell from this photo"]
}"""

JUDGE_PROMPT = """You are checking a description of a crop photograph written for a plant-pathology expert.
Required: every field filled with something specific (not 'unknown' or 'n/a'), a severity range in percent, an uncertainty list,
and NO crop name, disease name, pest name or cause anywhere in the text.
Return JSON only: {"passed": true|false, "missing": ["field names that fail"], "names_a_crop_or_disease": true|false,
"fixes": {"field name": "rewritten value without any names"}}"""

CHECK_PROMPT = """A farm photo was described as follows (appearance only):
{caption}

Candidate conditions of this crop, with their usual symptoms:
{options}

Score EACH candidate from 0 to 10 for how well it matches the description. Think about lesion colour, lesion shape, distribution on the plant,
severity, and anything in the description that CONTRADICTS the candidate (a contradiction lowers the score a lot). Do not give two candidates the
same high score unless they truly cannot be told apart from this description.
Return JSON only: {{"scores": {{"<condition id>": <0-10>, ...}}, "reason": "<one short sentence about the best match>"}}"""

GAP_MIN = 2.0        # the winner must lead the runner-up by at least this many points, else the photo cannot settle it


def enabled() -> bool:
    return os.getenv("CROPSY_CPJ", "on").lower() not in ("off", "0", "false")


def _json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n?", "", text).rstrip("`").strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(m.group()) if m else {}


def _catalog() -> dict:
    try:
        return json.loads((config.DATA_DIR / "issue_catalog.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


_NAMES: list[str] = []


def _leak_terms() -> list[str]:
    """Crop and disease names a caption must not contain."""
    if not _NAMES:
        names = {c.lower() for c in config.CROPS} | set(config.CROP_ALIASES) | {"paddy", "corn"}
        for meta in _catalog().values():
            lab = str(meta.get("label", "")).lower()
            if lab and lab != "healthy crop":
                names.add(lab)
        names |= {"blast", "blight", "sigatoka", "cordana", "tungro", "armyworm", "mosaic", "pestalotiopsis", "alternaria", "anthracnose", "smut", "red rot", "bud rot",
                  "fusarium", "powdery mildew", "downy mildew", "bacterial", "fungal", "virus", "viral", "nitrogen deficiency", "potassium deficiency", "zinc deficiency"}
        _NAMES.extend(sorted((n for n in names if len(n) >= 4), key=len, reverse=True))
    return _NAMES


def leaks(cap: dict) -> list[str]:
    text = " ".join(str(v) for v in cap.values()).lower()
    return [n for n in _leak_terms() if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", text)][:5]


def check(cap: dict) -> list[str]:
    """Deterministic quality gate: the names of fields that fail."""
    bad = []
    for f in FIELDS:
        v = cap.get(f)
        if v in (None, "", [], {}) or (isinstance(v, str) and v.strip().lower() in ("unknown", "n/a", "na", "none given", "not visible", "-")):
            if f in ("texture_or_growth", "insects_or_damage") and isinstance(v, str) and v.strip():
                continue
            bad.append(f)
    sev = str(cap.get("severity_percent", ""))
    if "severity_percent" not in bad and not re.search(r"\d", sev):
        bad.append("severity_percent")
    if str(cap.get("image_quality", "")).strip().lower() not in QUALITY and "image_quality" not in bad:
        bad.append("image_quality")
    return bad


def readable(cap: dict) -> list[str]:
    out = []
    for f in FIELDS:
        v = cap.get(f)
        if v in (None, "", []):
            continue
        out.append(f"{LABELS[f]}: " + ("; ".join(map(str, v)) if isinstance(v, list) else str(v)))
    return out


def summary(cap: dict) -> str:
    bits = [str(cap.get(k, "")) for k in ("lesion_colour", "lesion_shape", "distribution") if cap.get(k)]
    return ", ".join(bits)[:220]


def _trace(state: PipelineState, step: str, model: str, why: str, t0: float, out: str, cost: float, status: str = "ok") -> None:
    state.trace.append(TraceEntry(step=step, tool_or_model=model, why=why, status=status, latency_ms=(time.perf_counter() - t0) * 1000, est_cost_usd=cost,
                                  input_summary=f"image={state.image_name or 'uploaded'}", output_summary=out[:140]))
    state.total_cost_usd += cost


def _caption(state: PipelineState, feedback: str | None = None) -> dict:
    prompt = CAPTION_PROMPT + (f"\n\nYour previous description was rejected: {feedback}. Fix exactly these problems." if feedback else "")
    text, _ = bedrock.invoke_multimodal(config.MODEL_NOVA_LITE, prompt, state.image_bytes, image_format=state.image_format or "jpeg", max_tokens=450)
    return _json(text)


def _judge(cap: dict) -> dict:
    text, _tokens, _ = bedrock.invoke_text(config.MODEL_NOVA_MICRO, "DESCRIPTION:\n" + json.dumps(cap, ensure_ascii=False), system=JUDGE_PROMPT, max_tokens=350)
    return _json(text)


def run(state: PipelineState) -> bool:
    """Step 2a-2b. True when a caption was produced and judged (even if it still has gaps, which are shown); False means use the old vision step."""
    if not (state.image_bytes and enabled()):
        return False
    t0 = time.perf_counter()
    try:
        cap = _caption(state)
        if not cap:
            return False
        c_lite = config.COST_PER_1K.get(config.MODEL_NOVA_LITE, 0.00006)
        c_micro = config.COST_PER_1K.get(config.MODEL_NOVA_MICRO, 0.000035)
        _trace(state, "caption", config.MODEL_NOVA_LITE, "Describe the photo without naming any crop or disease", t0, summary(cap), c_lite)

        t1 = time.perf_counter()
        try:
            j = _judge(cap)
        except Exception as e:  # noqa: BLE001
            log.warning("Caption judge failed: %s (rules only)", e)
            j = {}
        fixed = []
        for f, val in (j.get("fixes") or {}).items():
            if f in FIELDS and val not in (None, ""):
                cap[f] = val
                fixed.append(f)
        issues = sorted(set(check(cap)) | ((set(j.get("missing") or []) & set(FIELDS)) - set(fixed)))
        leaked = leaks(cap)
        _trace(state, "caption_judge", config.MODEL_NOVA_MICRO, "Judge the caption: complete, severity given, uncertainty stated, no names", t1,
               f"passed={not (issues or leaked)} fixed={fixed} issues={issues} leaked={leaked}", c_micro)

        retried = False
        if issues or leaked:
            retried = True
            t2 = time.perf_counter()
            why = []
            if issues:
                why.append("these fields were missing or vague: " + ", ".join(issues))
            if leaked:
                why.append("do not use these words: " + ", ".join(leaked))
            cap2 = _caption(state, "; ".join(why))
            if cap2:
                issues2, leaked2 = check(cap2), leaks(cap2)
                _trace(state, "caption_retry", config.MODEL_NOVA_LITE, "Caption failed the judge: describe the photo once more", t2, f"issues={issues2} leaked={leaked2}", c_lite)
                if len(issues2) + len(leaked2) <= len(issues) + len(leaked):
                    cap, issues, leaked = cap2, issues2, leaked2
        state.visual_caption = {k: cap.get(k) for k in FIELDS}
        state.caption_judge = {"passed": not (issues or leaked), "missing": issues, "leaked": leaked, "fixed_fields": fixed, "retried": retried,
                               "checks": {"morphology": not {"lesion_colour", "lesion_shape", "distribution"} & set(issues), "severity": "severity_percent" not in issues,
                                          "uncertainty": "uncertainty" not in issues, "no_names": not leaked}}
        state.visual_observations = readable(cap)
        state.possible_symptom = summary(cap) or None
        state.diagnosis = None                                  # named later, from reference photos and passages, never from the caption alone
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("Caption step failed: %s (falling back to the one-shot vision step)", e)
        return False


def _top_condition(state: PipelineState) -> tuple[str | None, str | None, str | None]:
    ms = [m for m in (state.image_matches or []) if m.get("condition_code")]
    if not ms:
        return None, None, None
    votes: dict[str, list[float]] = {}
    for m in ms:
        votes.setdefault(m["condition_code"], []).append(float(m.get("similarity", 0.0)))
    code = sorted(votes.items(), key=lambda kv: (-len(kv[1]), -sum(kv[1]) / len(kv[1])))[0][0]
    first = next(m for m in ms if m["condition_code"] == code)
    return code, first.get("condition"), first.get("crop")


def agree(state: PipelineState) -> PipelineState:
    """Step 5b, after retrieval: score every candidate condition against the caption, then compare the winner with the nearest reference photos.
    A small lead (gap) between the best two candidates means the description cannot settle it: the answer is marked uncertain."""
    if not state.visual_caption:
        return state
    code, label, crop = _top_condition(state)
    if not code or code == "field_scene":
        return state
    t0 = time.perf_counter()
    try:
        cat = _catalog()
        opts = [(c, m) for c, m in cat.items() if m.get("crop") in (crop, "any") or c == "healthy"]
        options = "\n".join(f"- {c}: {m.get('label')}: " + "; ".join(m.get("symptoms") or []) for c, m in opts)
        prompt = CHECK_PROMPT.format(caption="\n".join(readable(state.visual_caption)), options=options)
        text, _tokens, _ = bedrock.invoke_text(config.MODEL_NOVA_MICRO, prompt, max_tokens=220)
        out = _json(text)
        valid = {c for c, _ in opts}
        scores = {}
        for k, v in (out.get("scores") or {}).items():
            try:
                if k in valid:
                    scores[k] = max(0.0, min(10.0, float(v)))
            except (TypeError, ValueError):
                continue
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        if not ranked:                                           # no usable scores: legacy single-choice answers still work
            choice = str(out.get("choice", "uncertain")).strip()
            ranked = [(choice, 10.0)] if choice in valid else []
        top, top_s = ranked[0] if ranked else ("uncertain", 0.0)
        second, second_s = ranked[1] if len(ranked) > 1 else (None, 0.0)
        gap = round(top_s - second_s, 1)
        # Measured on 20 held-out photos: the reference-photo match was right 19/20, the caption-only choice 10/20, and when the two disagreed the
        # reference match was right 9 of 10 times. So a disagreement must NOT lower trust in the photo match: it is shown as "not confirmed" only.
        if ranked and top == code and (len(ranked) < 2 or gap >= GAP_MIN):
            status = "agree"                                   # the description independently supports the reference match
        elif ranked and top == code:
            status = "uncertain"                               # same winner but too close to the runner-up
        else:
            status = "not_confirmed"                           # the description alone points elsewhere: informational
        top_label = cat.get(top, {}).get("label") if ranked else None
        table = [{"id": c, "label": cat.get(c, {}).get("label", c), "score": sc} for c, sc in ranked[:4]]
        state.visual_agreement = {"status": status, "caption_choice": top if ranked else "uncertain", "caption_choice_label": top_label, "reference_choice": code, "reference_label": label,
                                  "gap": gap, "scores": table, "confusable_with": cat.get(second, {}).get("label") if second else None, "reason": str(out.get("reason", ""))[:160]}
        if status == "agree":
            state.diagnosis = label
            state.image_consensus = (state.image_consensus or "") + " The photo description also fits this condition."
        _trace(state, "caption_check", config.MODEL_NOVA_MICRO, "Score each candidate condition against the caption, then compare with the reference photos", t0,
               f"{status}: top={top} gap={gap} reference={code}", config.COST_PER_1K.get(config.MODEL_NOVA_MICRO, 0.000035))
    except Exception as e:  # noqa: BLE001
        log.warning("Caption check failed: %s", e)
    return state


def report(state: PipelineState) -> dict | None:
    """The visual report shown to the farmer: caption fields, judge result, agreement."""
    if not state.visual_caption:
        return None
    return {"caption": [{"field": LABELS[f], "value": ("; ".join(map(str, v)) if isinstance(v, list) else str(v))} for f in FIELDS if (v := state.visual_caption.get(f)) not in (None, "", [])],
            "judge": state.caption_judge or {}, "agreement": state.visual_agreement, "models": {"caption": "Nova Lite", "judge": "Nova Micro", "check": "Nova Micro"}}
