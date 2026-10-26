"""When the guides have no answer Cropsy helps instead of stopping: what decides it, safe steps, one follow-up question, and never an estimated figure."""
import re

from app.pipeline import _NO_ANSWER_RX
from app.schemas import PipelineState
from app.steps import synthesize


def _model(monkeypatch, text):
    monkeypatch.setattr(synthesize.bedrock, "invoke_text", lambda *a, **k: (text, 0, 0.0))


HELP = ("EXPLAIN: The seed rate depends on the purpose of the crop, the variety and the planting method.\n"
        "- Check the seed packet or variety label.\n- Ask the nearest KVK.\n- Seed needed is 20 kg per hectare.\n- Use monocrotophos to protect seedlings.\n"
        "ASK: Is it for grain, fodder or vegetable?")


def test_missing_figure_gets_an_explanation_and_a_follow_up_question(monkeypatch):
    _model(monkeypatch, HELP)
    s = PipelineState(query="What is the seed rate for cowpea?", crop_hint="Cowpea")
    assert synthesize.help_without_evidence(s)
    assert "do not have this for cowpea" in s.raw_answer and s.raw_answer.rstrip().endswith("?")
    assert s.general_mode and len(s.recommendations) == 2


def test_no_figure_and_no_banned_chemical_can_slip_into_the_help(monkeypatch):
    _model(monkeypatch, HELP)
    s = PipelineState(query="What is the seed rate for cowpea?", crop_hint="Cowpea")
    synthesize.help_without_evidence(s)
    text = " ".join([s.raw_answer] + s.recommendations)
    assert not re.search(r"\d", text) and "monocrotophos" not in text.lower()


def test_figure_in_the_explanation_or_question_is_dropped(monkeypatch):
    _model(monkeypatch, "EXPLAIN: Use 20 kg.\n- Ask the KVK.\nASK: Is it 2 acres?")
    s = PipelineState(query="seed rate for cowpea", crop_hint="Cowpea")
    assert synthesize.help_without_evidence(s)
    assert not re.search(r"\d", s.raw_answer)


def test_model_failure_leaves_the_answer_unchanged(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(synthesize.bedrock, "invoke_text", boom)
    s = PipelineState(query="seed rate for cowpea", raw_answer="x")
    assert not synthesize.help_without_evidence(s) and s.raw_answer == "x"


def test_no_answer_wording_is_recognised_in_english_and_tamil():
    for t in ("The seed rate is not specified in the evidence.", "This figure is not provided in the TNAU guides", "The evidence does not explicitly state it, not explicitly mentioned",
              "தகவல் கிடைக்கவில்லை"):
        assert _NO_ANSWER_RX.search(t), t
    assert not _NO_ANSWER_RX.search("Sow 20 kg per hectare.")


def test_quantity_questions_are_recognised_in_three_languages():
    for q in ("What is the seed rate for cowpea?", "how much urea per acre", "uram evlo podanum", "விதை அளவு எவ்வளவு", "cowpea spacing"):
        assert synthesize._HIGH_IMPACT.search(q), q
    assert not synthesize._HIGH_IMPACT.search("how to control rice blast")


def test_dose_of_a_restricted_chemical_is_never_given_and_a_next_step_is_offered(monkeypatch):
    from tests.test_answer_policy import _model as model_mock
    from app import pipeline
    from app.schemas import AdvisoryRequest
    model_mock(monkeypatch, [{"answer": "Spray 500 ml per hectare of paraquat.", "recommendations": ["Paraquat 500 ml/ha"], "limitations": []}] * 3)
    r = pipeline.run(AdvisoryRequest(query="how much paraquat to spray on my rice"))
    assert "can't give a dose" in r.answer and not re.search(r"\d", " ".join([r.answer] + (r.recommendations or [])))
    assert r.confidence["level"] == "low" and not r.sources
