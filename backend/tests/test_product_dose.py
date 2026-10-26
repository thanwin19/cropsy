"""A dose belongs to its own product (release blocker found in the final review): numbers that exist in the guide for ANOTHER chemical are rejected."""
import json

from app import quantities as q

GUIDE = ("Spray any one of the following insecticides Chlorpyriphos 20 EC 3750 ml/ha Chlorantraniliprole 18.5% SC @150 ml/ha Flubendiamide 39.35%  SC 100ml/ha "
         "Spotted pod borer Thiodicarb 75% WP 625g/ha Pod bugs Dimethoate 30% EC 500ml/ha Methyl demeton 25% EC 500ml/ha")


def test_owners_are_read_with_decimals_and_formulations():
    assert q.dose_owners(GUIDE)[:3] == [("chlorpyriphos", (3750.0, "ml")), ("chlorantraniliprole", (150.0, "ml")), ("flubendiamide", (100.0, "ml"))]


def test_a_dose_taken_from_another_chemical_is_rejected():
    assert q.product_dose_mismatches("Use flubendiamide 39.35% SC at 150 ml/ha", [GUIDE]) == ["flubendiamide 150 ml"]
    assert q.product_dose_mismatches("Spray dimethoate 30 EC 625 ml/ha", [GUIDE]) == ["dimethoate 625 ml"]
    assert q.product_dose_mismatches("Chlorpyriphos 20 EC 100 ml/ha", [GUIDE])


def test_correct_pairings_and_units_pass():
    assert q.product_dose_mismatches("Use Chlorantraniliprole 18.5% SC @150 ml/ha or Flubendiamide 39.35% SC @100 ml/ha", [GUIDE]) == []
    assert q.product_dose_mismatches("Chlorpyriphos 20 EC 3.75 litre/ha; thiodicarb 0.625 kg/ha", [GUIDE]) == []   # g<->kg and ml<->l written the other way round


def test_unknown_product_is_left_to_the_other_checks():
    assert q.product_dose_mismatches("Use neem oil 3 ml/l", [GUIDE]) == []


def test_two_doses_for_one_product_in_the_guide_are_flagged_as_ambiguous():
    twice = GUIDE + " Chlorantraniliprole 18.5%  SC  100ml/ha"
    assert q.ambiguous_products("Chlorantraniliprole 18.5% SC @150 ml/ha", [twice]) == ["chlorantraniliprole"]
    assert q.ambiguous_products("Flubendiamide 39.35% SC @100 ml/ha", [twice]) == []


def test_real_blackgram_passage_binds_each_product():
    for c in map(json.loads, open("knowledge/chunks.jsonl", encoding="utf-8")):
        if c["chunk_id"] == "blackgram-001-p152-018":
            assert q.product_dose_mismatches("Flubendiamide 39.35% SC @100 ml/ha; lufenuron 5.4% EC 600 ml/ha", [c["text"]]) == []
            assert q.product_dose_mismatches("Lufenuron 5.4% EC 100 ml/ha", [c["text"]]) == ["lufenuron 100 ml"]


def _state(answer, retry):
    from app.schemas import PipelineState
    s = PipelineState(query="blackgram insect control", crop_hint="Blackgram")
    s.chunks = [{"crop": "Blackgram", "text": GUIDE, "title": "Guide", "page": 152, "relevance_score": 0.8}]
    s.raw_answer, s.recommendations, s.retry_count, s.route = answer, ["Spray flubendiamide 39.35% SC at 150 ml/ha."], retry, "ADVISORY"
    return s


def test_verifier_asks_for_a_retry_then_removes_the_misbound_dose():
    from app.steps import verify
    s = verify.run(_state("Use flubendiamide at 150 ml/ha for pod borer.", 0))
    assert s.verification_status == "needs_retry" and any("V14_PRODUCT_DOSE" in f for f in s.verification_flags)
    s = verify.run(_state("Use flubendiamide at 150 ml/ha for pod borer. Neem oil is also used.", 1))
    assert "150" not in (s.raw_answer or "") and not any("150" in r for r in s.sanitized_recommendations)
    assert any("did not match the guide" in x for x in s.limitations)


def test_a_correct_answer_passes_without_a_retry():
    from app.steps import verify
    st = _state("Use flubendiamide 39.35% SC @100 ml/ha for pod borer.", 0)
    st.recommendations = ["Spray flubendiamide 39.35% SC at 100 ml/ha."]
    s = verify.run(st)
    assert not any("V14" in f for f in s.verification_flags)
