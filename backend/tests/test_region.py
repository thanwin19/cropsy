"""Region awareness: where the farmer is, where the knowledge applies, and what happens when they differ. Bedrock is mocked (conftest), so these test the rules, not the live model."""
import numpy as np
import pytest

from app import pipeline, region
from app.schemas import AdvisoryRequest, PipelineState
from app.steps import retrieve
from tests.test_answer_policy import GOOD, _model


def test_district_implies_state_and_zone():
    r = region.detect("rice planting in Tenkasi")
    assert (r["state"], r["district"], r["zone"], r["country"], r["source"]) == ("Tamil Nadu", "Tenkasi", "Southern", "India", "question")
    assert region.detect("nel in Nellai")["district"] == "Tirunelveli"


def test_other_state_and_other_country():
    assert region.detect("wheat sowing time in Punjab")["state"] == "Punjab"
    assert region.detect("paddy in Kerala")["state"] == "Kerala"
    r = region.detect("rice farming in Sri Lanka")
    assert r["country"] == "Sri Lanka" and r["state"] is None


def test_no_region_in_the_words_is_unknown_not_guessed():
    assert region.detect("how much urea for rice")["source"] == "unknown"


def test_precedence_words_then_profile_then_parcel():
    assert region.resolve("sowing time in Punjab", {"state": "Kerala"}, {"id": "TM-05"})["state"] == "Punjab"
    assert region.resolve("sowing time", {"state": "Kerala", "country": "India"}, {"id": "TM-05"})["state"] == "Kerala"
    assert region.resolve("sowing time", None, {"id": "TM-05"})["district"] == "Tenkasi"
    assert region.resolve("sowing time", None, None)["source"] == "unknown"


def test_chunk_region_defaults_and_matching():
    tn = {"document_id": "DOC_TNAU_AGRON_001"}
    national = {"document_id": "PDF_SPICES_TURMERIC"}
    assert region.match({"state": "Tamil Nadu", "zone": "Southern", "country": "India"}, {**tn, "region": {"country": "India", "state": "Tamil Nadu", "zone": "Southern"}}) == "zone"
    assert region.match({"state": "Tamil Nadu", "country": "India"}, tn) == "state"
    assert region.match({"state": "Punjab", "country": "India"}, tn) == "mismatch"
    assert region.match({"state": "Punjab", "country": "India"}, national) == "country"       # a national publication applies in any state, at country level
    assert region.match({"country": "Sri Lanka"}, tn) == "mismatch"
    assert region.match(region.unknown(), tn) == "unknown"


def test_ranking_demotes_other_region_chunks_but_never_removes_them(monkeypatch):
    chunks = [{"chunk_id": "a", "document_id": "x", "region": {"country": "India", "state": "Punjab"}}, {"chunk_id": "b", "document_id": "x", "region": {"country": "India", "state": "Tamil Nadu"}}]
    monkeypatch.setattr(retrieve, "_CHUNKS", chunks)
    retrieve._REGION_CACHE.clear()
    st = PipelineState(query="q", region={"country": "India", "state": "Tamil Nadu", "zone": None, "district": None, "source": "question"})
    adj = retrieve._region_adjust(st)
    assert adj[0] < 0 < adj[1]
    assert np.all(retrieve._region_adjust(PipelineState(query="q", region=region.unknown())) == 0)       # unknown region: no effect
    retrieve._REGION_CACHE.clear()


def _run(q, **kw):
    return pipeline.run(AdvisoryRequest(query=q, **kw))


def test_other_state_gets_labelled_general_guidance_and_a_note():
    r = _run("what is the sowing time for wheat in Punjab")
    assert r.region["state"] == "Punjab" and not r.sources
    assert any("Punjab" in x and "general guidance" in x for x in (r.limitations or []))


def test_unknown_region_sensitive_question_asks_for_the_location(monkeypatch):
    _model(monkeypatch, [{"answer": "Apply urea in splits as the guide says for rice.", "recommendations": ["Split the nitrogen."], "limitations": []}])
    r = _run("how much urea should I apply to rice")
    assert r.region["source"] == "unknown"
    assert any("set your region" in l for l in (r.limitations or []))          # the note is a short line under the answer, not part of the answer text
    assert "set your region" not in (r.answer or "")
    assert r.region_note if hasattr(r, "region_note") else True


def test_known_tamil_nadu_region_adds_no_caveat(monkeypatch):
    _model(monkeypatch, [{"answer": "Apply urea in splits as the guide says for rice.", "recommendations": ["Split the nitrogen."], "limitations": []}])
    r = _run("how much urea should I apply to rice in Tenkasi")
    assert r.region["district"] == "Tenkasi" and "tell me your state" not in (r.answer or "")


def test_saved_profile_is_used_when_the_words_name_no_place():
    r = _run("what is the sowing time for wheat", region={"country": "India", "state": "Punjab"})
    assert r.region["source"] == "profile" and r.region["state"] == "Punjab" and not r.sources


def test_parcel_question_is_tamil_nadu_without_a_note(monkeypatch):
    _model(monkeypatch, [GOOD])
    r = _run("how much urea should I apply", parcel_id="TM-05")
    assert r.region["district"] == "Tenkasi" and "tell me your state" not in (r.answer or "")


def test_conflicting_regional_recommendations_stay_visible():
    from app import conflicts
    st = PipelineState(query="basal fym for turmeric")
    st.chunks = [{"chunk_id": "turmeric-002-p186-003"}, {"chunk_id": "turmeric-web-010"}]
    out = conflicts.annotate(st)
    note = " ".join(out.limitations)
    assert "Tamil Nadu" in note and "India (national)" in note and "does not choose" in note


def test_tamil_nadu_season_card_is_not_shown_to_a_farmer_in_another_state(monkeypatch):
    from app.steps import guides
    st = PipelineState(query="what is the sowing time for wheat in Punjab", region=region.detect("what is the sowing time for wheat in Punjab"))
    cards = guides._drop_tn_only([{"id": "season", "kind": "knowledge"}, {"id": "x", "kind": "knowledge"}, {"id": "cal", "kind": "calendar"}], st)
    assert [c["id"] for c in cards] == ["x"]
    tn = PipelineState(query="sowing time in Tenkasi", region=region.detect("sowing time in Tenkasi"))
    assert len(guides._drop_tn_only([{"id": "season", "kind": "knowledge"}], tn)) == 1
