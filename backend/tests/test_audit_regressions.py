"""Regression tests from the chatbox correctness audit (offline: no AWS calls). Each one is a failure found by reading real answers."""
import numpy as np

from app.pipeline import _build_sources
from app.schemas import PipelineState
from app.steps import hybrid, tools, understand


def test_tanglish_fertilizer_word_is_not_read_as_water():           # "uram evlo podanum nel ku" was answered with irrigation advice
    assert understand._topic_from_words("uram evlo podanum nel ku")[0] == "fertilizer"


def test_tanglish_insect_medicine_is_a_pest_question():             # "ulundhu pooch marundhu" was answered with the flowering time
    assert understand._topic_from_words("ulundhu pooch marundhu")[0] == "pest"
    assert understand._topic_from_words("மிளகாய் பூச்சி மருந்து")[0] == "pest"


def test_medicine_alone_asks_for_a_spray():
    assert understand._topic_from_words("tomato ku enna marundhu adikkanum")[0] == "spray"


def test_plain_english_has_no_forced_topic():
    assert understand._topic_from_words("how to control sheath blight in rice") is None


def test_parcel_named_in_words_is_found():                          # "TM-05 satellite health" reached the model as general guidance
    assert tools.parcel_from_text("TM-05 satellite health this week") == "TM-05"
    assert tools.parcel_from_text("is tm 12 stressed") == "TM-12"
    assert tools.parcel_from_text("TM-999 satellite") is None
    assert tools.parcel_from_text("rice blast") is None


def test_no_source_is_cited_beside_a_no_information_answer():      # cowpea seed rate cited a page while saying the guide has no seed rate
    s = PipelineState(query="seed rate for cowpea")
    s.raw_answer = "The seed rate for cowpea is not specified in the provided evidence."
    s.chunks = [{"document_id": "d", "page": 169, "title": "Crop Production Guide", "relevance_score": 0.67}]
    assert _build_sources(s) == []
    s.raw_answer = "Sow cowpea at 20 kg/ha."
    assert len(_build_sources(s)) == 1


def test_rare_question_word_lifts_the_chunk_that_contains_it():     # "rice blast control" ranked a variety note above the blast sprays
    chunks = [{"crop": "Rice", "text": "variety note susceptible to blast"}, {"crop": "Rice", "text": "spray tricyclazole for blast"}] + [{"crop": "Rice", "text": f"filler text {i}"} for i in range(60)]
    b = hybrid.term_bonus("tricyclazole spray", chunks)
    assert b[1] > 0 and b[0] == 0 and isinstance(b, np.ndarray)


def test_followup_detection_needs_a_cue_and_no_crop():
    assert understand._is_followup("and the seed rate?") and understand._is_followup("what about its spacing")
    assert not understand._is_followup("PM Kisan eligibility") and not understand._is_followup("wheat seed rate")


def test_crop_dependent_question_without_a_crop_asks_which_crop():  # "what is the seed rate" was answered with rice and maize figures
    from app.steps import guides_dynamic as gd
    assert gd._needs_crop(PipelineState(query="what is the seed rate"), "what is the seed rate")
    assert not gd._needs_crop(PipelineState(query="seed rate for wheat"), "seed rate for wheat")
    assert not gd._needs_crop(PipelineState(query="and the seed rate?", crop_hint="Wheat"), "and the seed rate?")
