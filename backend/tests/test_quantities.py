"""Numbers must keep their context: basis (per hectare, per cent, per litre), presence in the evidence, and the page that proves them."""
import json

from app import quantities as q
from app.pipeline import _build_sources
from app.schemas import PipelineState

NURSERY = "Sow 3.75 kg of seeds in 7.5 cents (0.5 kg / cent) and use increased seed rate upto 12.5 kg per ha in shootfly endemic area."


def test_nursery_rate_is_not_a_per_hectare_rate():                   # the pearl millet mix-up
    assert q.basis_mismatches("seed rate 3.75 kg to 12.5 kg per hectare", [NURSERY])
    assert q.basis_mismatches("கம்பு விதை ஒரு எக்டருக்கு சுமார் **3.75 கிலோ முதல் 12.5 கிலோ** வரை", [NURSERY])
    assert not q.basis_mismatches("3.75 kg per 7.5 cents; up to 12.5 kg per hectare in shootfly areas", [NURSERY])


def test_a_figure_not_in_the_evidence_is_reported():                 # "increase to 10 kg" where the source says 12.5 kg
    assert q.unsupported("increase the seed rate to 10 kg per hectare", [NURSERY]) == ["10 kg"]
    assert q.unsupported("increase the seed rate to 12.5 kg per hectare", [NURSERY]) == []


def test_unit_conversions_are_allowed():
    assert q.unsupported("500 g per hectare", ["carbendazim 0.5 kg/ha"]) == []
    assert q.unsupported("2 ml per litre", ["2 ml/l"]) == []


def test_spacing_and_percent_are_checked():                          # cowpea spacing was filled in from the model's own knowledge
    assert set(q.unsupported("spacing 30 x 10 cm", ["rows 45 x 15 cm"])) == {"30 cm", "10 cm"}
    assert q.unsupported("spray 0.3% mancozeb", ["mancozeb 0.2 %"]) == ["0.3 %"]


def test_citation_is_the_page_that_contains_the_figure():            # wheat seed rate cited the page about fertilizer
    s = PipelineState(query="wheat seed rate")
    s.raw_answer = "The wheat seed rate is 100 kg/ha."
    s.chunks = [
        {"document_id": "d", "page": 135, "title": "Guide", "relevance_score": 0.54, "text": "blanket recommendation of 80:40:40 NPK kg/ha. Apply 37.5 kg ZnSO4"},
        {"document_id": "d", "page": 134, "title": "Guide", "relevance_score": 0.50, "text": "3. SEED RATE: 100 kg/ha"},
    ]
    assert [x.page for x in _build_sources(s)] == ["134"]


def test_date_claims_find_their_page():
    s = PipelineState(query="wheat sowing time")
    s.raw_answer = "Sow wheat from 15th October to the first week of November."
    s.chunks = [{"document_id": "d", "page": 136, "title": "Guide", "relevance_score": 0.6, "text": "Draw the lines 20 cm apart"},
                {"document_id": "d", "page": 134, "title": "Guide", "relevance_score": 0.5, "text": "Ideal sowing time is 15th October to 1st week of November"}]
    assert [x.page for x in _build_sources(s)] == ["134"]


def test_gold_set_is_well_formed():
    d = json.load(open("tests/gold_set.json", encoding="utf-8"))["questions"]
    assert len(d) >= 20 and all({"id", "q", "behavior"} <= set(x) for x in d)
    assert {x["behavior"] for x in d} <= {"answer", "no_info", "clarify", "general", "card"}


def test_a_figure_for_another_purpose_is_not_a_seed_rate():          # cowpea "seed rate 2 kg/ha" was phosphobacteria
    ev = ["Apply 10 packets (2 kg/ha) of Phosphobacteria with 25 kg of FYM before sowing.", "3. SEED RATE: 100 kg/ha"]
    assert q.purpose_mismatches("The seed rate for cowpea is 2 kg/ha.", "seed rate for cowpea", ev)
    assert not q.purpose_mismatches("The seed rate is 100 kg/ha.", "wheat seed rate", ev)


def test_verifier_second_pass_removes_a_figure_with_the_wrong_basis():
    from app.steps import verify
    s = PipelineState(query="pearl millet seed rate", crop_hint="Cumbu")
    s.chunks = [{"crop": "Cumbu", "text": NURSERY, "title": "Guide", "page": 95, "relevance_score": 0.8}]
    s.raw_answer = "Seed rate is 3.75 kg per hectare. Sow in rows with care."
    s.recommendations = ["Use 3.75 kg per hectare of seed."]
    s.route = "ADVISORY"
    s.retry_count = 0
    first = verify.run(s)
    assert first.verification_status == "needs_retry"
    s.retry_count = 1
    second = verify.run(s)
    assert "3.75" not in (second.raw_answer or "") and not any("3.75" in r for r in second.sanitized_recommendations)


def test_a_sentence_pointing_at_a_removed_figure_is_removed_too():
    from app.steps.verify import _drop_sentences_with
    assert _drop_sentences_with("Plant at 30 x 10 cm. This spacing is standard for optimal yield.", ["10 cm"]) == ""
    assert _drop_sentences_with("Plant at 30 x 10 cm. Water weekly.", ["10 cm"]) == "Water weekly."


def test_off_topic_answer_to_a_spacing_question_becomes_no_information():   # cowpea spacing was answered with seed-production hygiene
    from app.steps import verify
    s = PipelineState(query="cowpea spacing", crop_hint="Cowpea")
    s.chunks = [{"crop": "Cowpea", "text": "Land should be free of volunteer plants. Clip tendrils.", "title": "Guide", "page": 168, "relevance_score": 0.5}]
    s.raw_answer = "Ensure the land is free of volunteer cowpea plants and avoid planting the same variety consecutively."
    s.recommendations, s.route, s.retry_count = ["Clip tendrils."], "ADVISORY", 0
    out = verify.run(s)
    assert "not provided" in out.raw_answer and out.recommendations == []
