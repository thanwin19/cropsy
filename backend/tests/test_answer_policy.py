"""Verifier and retry policy: useful answers survive, unsafe content does not. Bedrock is mocked (no AWS); these are policy tests, not live-model tests."""
import json

import pytest

from app import config, pipeline
from app.schemas import AdvisoryRequest, PipelineState
from app.steps import verify


def _state(answer, recs=(), satellite=None):
    s = PipelineState(query="q", parcel_id="TM-14")
    s.route = config.ROUTE_ADVISORY
    s.parcel_context = {"parcel_id": "TM-14", "data_source": "dummy", "crop": {"name": "Banana", "variety": "Nendran", "stage": "Vegetative", "days_after_planting": 70}}
    s.chunks = [{"text": "Apply 45 kg/ha nitrogen.", "title": "CPG", "page": 1}]
    s.raw_answer, s.recommendations = answer, list(recs)
    s.satellite = satellite
    return s


def _model(monkeypatch, replies):
    """Make every synthesis call return the next reply (a dict, a string, or an Exception to raise)."""
    import app.models.bedrock as bm
    seq = list(replies)
    real = bm.invoke_text

    def fake(model_id, prompt, system=None, **kw):
        if system and "Return JSON only" in (system or "") or "normalized_query" in (system or ""):
            return real(model_id, prompt, system=system, **kw)       # the understand step keeps the conftest mock
        r = seq.pop(0) if len(seq) > 1 else seq[0]
        if isinstance(r, Exception):
            raise r
        return (r if isinstance(r, str) else json.dumps(r)), 100, 5.0
    monkeypatch.setattr(bm, "invoke_text", fake)


GOOD = {"answer": "Vegetative stage banana: keep the soil moist and remove old leaves.", "recommendations": ["Remove old leaves."], "limitations": []}
BAD_DOSE = {"answer": "Vegetative stage banana. Spray mancozeb at 9 g/l now to protect the crop.", "recommendations": ["Spray mancozeb at 9 g/l."], "limitations": []}


def test_valid_answer_passes_unchanged():
    out = verify.run(_state("Vegetative stage, 70 days after planting. Keep the soil moist.", ["Remove old leaves."]))
    assert out.verification_status == "pass" and "Keep the soil moist" in out.raw_answer


def test_unsupported_dose_is_masked_with_a_next_step_and_the_rest_is_kept():
    out = verify.run(_state("Vegetative stage. Spray mancozeb at 9 g/l now. Also remove old leaves.", ["Spray mancozeb at 9 g/l."]))
    assert out.verification_status == "needs_retry"
    assert "9 g/l" not in out.raw_answer and "confirm with your KVK" in out.raw_answer and "remove old leaves" in out.raw_answer


def test_empty_answer_needs_retry():
    assert verify.run(_state("", [])).verification_status == "needs_retry"


def test_successful_retry_returns_the_corrected_answer(monkeypatch):
    _model(monkeypatch, [BAD_DOSE, GOOD])
    r = pipeline.run(AdvisoryRequest(query="banana leaf spot what to spray", parcel_id="TM-14"))
    assert "9 g/l" not in (r.answer or "") and "old leaves" in (r.answer or "")


def test_failed_retry_keeps_the_answer_and_says_what_is_uncertain(monkeypatch):
    _model(monkeypatch, [BAD_DOSE, BAD_DOSE])
    r = pipeline.run(AdvisoryRequest(query="banana leaf spot what to spray", parcel_id="TM-14"))
    assert r.answer and "mancozeb" in r.answer.lower() and "9 g/l" not in r.answer           # useful text kept, the unsupported number gone
    assert any("KVK" in x for x in (r.limitations or []))                                    # the uncertainty is stated
    assert r.verified is False                                                               # never marked verified


def test_prohibited_pesticide_is_removed_after_a_failed_retry_and_the_rest_is_kept(monkeypatch):
    _model(monkeypatch, [{"answer": "Vegetative stage banana. Use endosulfan on the leaves. Also remove old leaves and keep the field weed free.", "recommendations": ["Use endosulfan.", "Remove old leaves."], "limitations": []}])
    r = pipeline.run(AdvisoryRequest(query="banana pest what to spray", parcel_id="TM-14"))
    assert "endosulfan" not in (r.answer or "").lower() and all("endosulfan" not in x.lower() for x in (r.recommendations or []))
    assert "remove old leaves" in (r.answer or "").lower() or any("old leaves" in x.lower() for x in (r.recommendations or []))
    assert any("banned" in x.lower() for x in (r.limitations or []))


def test_prohibited_pesticide_is_first_sent_back_for_correction(monkeypatch):
    _model(monkeypatch, [{"answer": "Vegetative stage banana. Use endosulfan on the leaves.", "recommendations": ["Use endosulfan."], "limitations": []}, GOOD])
    r = pipeline.run(AdvisoryRequest(query="banana pest what to spray", parcel_id="TM-14"))
    assert "endosulfan" not in (r.answer or "").lower() and "old leaves" in (r.answer or "")


def test_warning_that_endosulfan_is_banned_is_not_treated_as_a_recommendation():
    out = verify.run(_state("Vegetative stage, 70 days after planting. Endosulfan is banned in India and must not be used.", []))
    assert out.verification_status != "needs_retry"


def test_tamil_spelling_of_a_banned_chemical_is_caught():
    from app import pesticides
    assert any(k == "banned" for _n, k, _x in pesticides.mentioned("எண்டோசல்பான் 35 எசிஎஸ் தெளிக்கவும்"))


def test_valid_low_confidence_answer_is_still_returned(monkeypatch):
    _model(monkeypatch, [GOOD])
    r = pipeline.run(AdvisoryRequest(query="tell me about my banana", parcel_id="TM-14"))
    assert (r.answer or "").strip() and r.confidence is not None


def test_model_exception_gives_a_real_message_not_a_blank(monkeypatch):
    _model(monkeypatch, [RuntimeError("timeout")])
    r = pipeline.run(AdvisoryRequest(query="banana leaf spot what to spray", parcel_id="TM-14"))
    assert (r.answer or "").strip()


def test_empty_model_reply_is_not_shown_as_a_verified_answer(monkeypatch):
    _model(monkeypatch, [""])
    r = pipeline.run(AdvisoryRequest(query="banana leaf spot what to spray", parcel_id="TM-14"))
    assert (r.answer or "").strip() and r.verified is False


SAT = {"latest_ndvi": 0.2653, "canonical": {"status": "normal", "change_vs_baseline": -0.007,
       "latest_scene": {"date": "2026-09-29", "indices": {"ndvi": 0.2653}}, "monthly_composite": {"month": "2026-09", "mean": 0.269}}}


@pytest.mark.parametrize("answer,ok", [
    ("The latest scene on 2026-09-29 shows NDVI 0.2653; the change is small.", True),
    ("NDVI is 0.71 on 2026-09-29, a healthy crop.", False),                                       # a number the evidence does not contain
    ("The monthly composite NDVI 0.2653 shows the field is fine.", False),                        # latest-scene value called monthly
    ("The vegetation is decreasing, NDVI 0.2653 on 2026-09-29.", False),                          # decrease claimed while status is normal
])
def test_satellite_values_and_wording_are_checked(answer, ok, monkeypatch):
    from app import field_analysis
    monkeypatch.setattr(field_analysis, "evidence_text", lambda pid, with_zones=False: "NDVI 0.2653 baseline 0.272 change -0.007 monthly 0.269")
    out = verify.run(_state("Vegetative stage, 70 days after planting. " + answer, [], satellite=SAT))
    assert (out.verification_status != "needs_retry") is ok
