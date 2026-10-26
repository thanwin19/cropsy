"""Tests for the Caption, Judge, Check steps (app/steps/caption.py) with the model calls mocked: no AWS needed."""
from __future__ import annotations

import json

import pytest

from app import config
from app.models import bedrock
from app.schemas import PipelineState
from app.steps import caption

GOOD = {"plant_part": "leaf", "lesion_colour": "grey-white centre with brown edge", "lesion_shape": "spindle", "margin_and_halo": "brown margin, faint yellow ring",
        "distribution": "scattered along the leaf between veins", "texture_or_growth": "dry, no coating", "insects_or_damage": "none visible", "severity_percent": "20-30",
        "image_quality": "good", "uncertainty": ["lower leaf is out of focus"]}


def _state():
    return PipelineState(query="what is this", image_bytes="AAAA", image_format="jpeg", image_name="t.jpg")


@pytest.fixture
def fake(monkeypatch):
    """captions: list of dicts returned in order; judge: dict returned for every judge call."""
    box = {"captions": [GOOD], "judge": {"passed": True, "missing": [], "fixes": {}}, "calls": {"caption": 0, "judge": 0, "check": 0}, "check": {"choice": "uncertain", "reason": ""}}

    def mm(model, prompt, img, image_format="jpeg", max_tokens=0):
        box["calls"]["caption"] += 1
        caps = box["captions"]
        return json.dumps(caps[min(box["calls"]["caption"] - 1, len(caps) - 1)]), 1.0

    def tx(model, prompt, max_tokens=0, system=None, temperature=0.2):
        if "CHECK" in (system or "") or "Candidate conditions" in prompt:
            box["calls"]["check"] += 1
            return json.dumps(box["check"]), 10, 1.0
        box["calls"]["judge"] += 1
        return json.dumps(box["judge"]), 10, 1.0

    monkeypatch.setattr(bedrock, "invoke_multimodal", mm)
    monkeypatch.setattr(bedrock, "invoke_text", tx)
    return box


def test_good_caption_passes_without_retry(fake):
    s = _state()
    assert caption.run(s) is True
    assert s.caption_judge["passed"] and not s.caption_judge["retried"]
    assert fake["calls"] == {"caption": 1, "judge": 1, "check": 0}
    assert s.diagnosis is None and s.visual_observations and "spindle" in (s.possible_symptom or "")


def test_caption_that_names_a_disease_is_rejected_and_redone(fake):
    leaky = dict(GOOD, lesion_shape="classic rice blast diamond lesion")
    fake["captions"] = [leaky, GOOD]
    s = _state()
    assert caption.run(s)
    assert s.caption_judge["retried"] and s.caption_judge["passed"] and not s.caption_judge["leaked"]
    assert fake["calls"]["caption"] == 2


def test_missing_field_is_filled_by_the_judge_without_a_retry(fake):
    partial = dict(GOOD, margin_and_halo="unknown")
    fake["captions"] = [partial]
    fake["judge"] = {"passed": False, "missing": ["margin_and_halo"], "fixes": {"margin_and_halo": "brown edge, no halo"}}
    s = _state()
    assert caption.run(s)
    assert "margin_and_halo" in s.caption_judge["fixed_fields"]
    assert s.caption_judge["passed"] and not s.caption_judge["retried"]


def test_still_failing_caption_is_reported_not_hidden(fake):
    bad = dict(GOOD, severity_percent="a lot", uncertainty=[])
    fake["captions"] = [bad, bad]
    s = _state()
    assert caption.run(s)
    assert not s.caption_judge["passed"] and "severity_percent" in s.caption_judge["missing"]


def test_caption_failure_returns_false_so_the_old_vision_step_runs(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no network")
    monkeypatch.setattr(bedrock, "invoke_multimodal", boom)
    assert caption.run(_state()) is False


def test_switch_off(monkeypatch):
    monkeypatch.setenv("CROPSY_CPJ", "off")
    assert caption.run(_state()) is False


def _with_matches(state, code="rice_blast", label="Rice blast", crop="Rice"):
    state.image_matches = [{"condition_code": code, "condition": label, "crop": crop, "similarity": 0.8}] * 3
    state.image_consensus = "3 of 3 nearest reference photos show Rice - Rice blast"
    return state


def test_agreement_when_caption_and_reference_photos_match(fake):
    s = _state()
    caption.run(s)
    _with_matches(s)
    fake["check"] = {"scores": {"rice_blast": 8, "rice_narrow_brown_spot": 3, "healthy": 0}, "reason": "spindle lesions with brown edge"}
    caption.agree(s)
    assert s.visual_agreement["status"] == "agree" and s.diagnosis == "Rice blast"


def test_disagreement_is_shown_but_does_not_force_uncertainty(fake):
    s = _state()
    caption.run(s)
    _with_matches(s)
    fake["check"] = {"scores": {"rice_narrow_brown_spot": 8, "rice_blast": 3}, "reason": "narrow streaks"}
    caption.agree(s)
    assert s.visual_agreement["status"] == "not_confirmed"
    assert "uncertain" not in (s.image_consensus or "") and not s.limitations and s.diagnosis is None


def test_unknown_condition_ids_are_ignored(fake):
    s = _state()
    caption.run(s)
    _with_matches(s)
    fake["check"] = {"scores": {"made_up_disease": 9}, "reason": ""}
    caption.agree(s)
    assert s.visual_agreement["status"] == "not_confirmed" and not s.visual_agreement["scores"]


def test_leak_and_check_helpers():
    assert "rice" in caption.leaks({"a": "this looks like rice blast"}) or "rice blast" in caption.leaks({"a": "this looks like rice blast"})
    assert caption.leaks(GOOD) == []
    assert caption.check(GOOD) == []
    assert "image_quality" in caption.check(dict(GOOD, image_quality="excellent"))
    assert set(caption.check({})) == set(caption.FIELDS)


def test_a_small_lead_between_two_conditions_is_uncertain(fake):
    s = _state()
    caption.run(s)
    _with_matches(s)
    fake["check"] = {"scores": {"rice_blast": 7, "rice_narrow_brown_spot": 6.5}, "reason": "both fit"}
    caption.agree(s)
    va = s.visual_agreement
    assert va["status"] == "uncertain" and va["gap"] == 0.5 and va["confusable_with"]
    assert s.visual_agreement["scores"]


def test_old_single_choice_answer_still_works(fake):
    s = _state()
    caption.run(s)
    _with_matches(s)
    fake["check"] = {"choice": "rice_blast", "reason": "x"}
    caption.agree(s)
    assert s.visual_agreement["status"] == "agree"
