"""The parcel fertilizer answer comes from the calculator: per-hectare recommendation, parcel area and parcel totals are never mixed (release blocker found in the final review)."""
from app.schemas import PipelineState
from app.steps import calculator


def _state(area):
    s = PipelineState(query="how much urea and dap per acre for maize", parcel_id="TM-31")
    s.parcel_context = {"parcel_id": "TM-31", "area_ha": area, "crop": {"name": "Rice"}}
    s.chunks = [{"text": "Blanket recommendation : 75:25:37.5 kg N:P2O5:K2O /ha", "title": "Guide", "page": 48}, {"text": "50:25:25 kg N:P2O5:K2O /ha", "title": "Guide", "page": 46}]
    return calculator.run(s)


def test_totals_are_the_per_hectare_figure_times_the_area():
    s = _state(1.3)
    o = s.calc["options"][0]
    assert (o["N_kg"], o["P2O5_kg"], o["K2O_kg"]) == (98, 32, 49)                    # 75 x 1.3, 25 x 1.3, 37.5 x 1.3
    head, recs = calculator.answer_from_calculator(s)
    assert "1.3 ha" in head and "98 kg" in recs[0] and "per ha" in recs[0] and "whole parcel" in recs[0]


def test_every_option_is_stated_with_its_own_totals_and_source():
    head, recs = calculator.answer_from_calculator(_state(1.3))
    assert "75:25:37.5" in recs[0] and "p.48" in recs[0] and "50:25:25" in recs[1] and "p.46" in recs[1]
    assert "N 65 kg" in recs[1] and "K2O 32 kg" in recs[1]                            # option 2 keeps option 2's numbers


def test_small_and_large_parcels_scale_linearly():
    small = _state(0.2).calc["options"][1]
    large = _state(50).calc["options"][1]
    assert (small["N_kg"], large["N_kg"]) == (10, 2500) and large["urea_kg"] > 100 * small["urea_kg"] / 2


def test_no_area_or_invalid_area_gives_no_totals():
    assert calculator.run(PipelineState(query="how much urea", parcel_context={"parcel_id": "TM-1"})).calc is None
    assert calculator.answer_from_calculator(_state(0)) is None
    assert calculator.answer_from_calculator(_state(-3)) is None
    assert calculator.answer_from_calculator(_state(20000)) is None


def test_no_recommendation_in_the_evidence_gives_no_written_answer():
    s = PipelineState(query="how much urea", parcel_id="TM-31")
    s.parcel_context = {"parcel_id": "TM-31", "area_ha": 1.0, "crop": {"name": "Rice"}}
    s.chunks = [{"text": "irrigate weekly", "title": "Guide", "page": 1}]
    assert calculator.answer_from_calculator(calculator.run(s)) is None
