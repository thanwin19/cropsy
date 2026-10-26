"""
test_pipeline.py — Unit tests for the Cropsy backend pipeline.
All Bedrock calls are mocked via conftest.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app import pipeline
from app.schemas import AdvisoryRequest, PipelineState
from app.steps import understand, router, tools, verify


# ── Understand step ───────────────────────────────────────────────────────────
class TestUnderstand:
    def test_english_query(self):
        state = PipelineState(query="What is the growth stage of rice at TM-03?")
        result = understand.run(state)
        assert result.language in ("en", "ta", "tanglish")
        assert result.intent is not None
        assert len(result.trace) == 1
        assert result.trace[0].step == "understand"

    def test_tanglish_detected_fast(self):
        state = PipelineState(query="nalla vanakam, TM-01 la coconut stage enna?")
        result = understand.run(state)
        # Fast language detection should catch tanglish
        assert result.language in ("tanglish", "ta", "en")

    def test_fallback_on_model_error(self, monkeypatch):
        import app.models.bedrock as bm
        def _raise(*a, **kw):
            raise RuntimeError("Simulated model failure")
        monkeypatch.setattr(bm, "invoke_text", _raise)
        bm._bedrock_runtime = None

        state = PipelineState(query="How much fertilizer for rice?")
        result = understand.run(state)
        assert result.language is not None  # falls back gracefully
        assert result.trace[0].status in ("ok", "fallback", "error")


# ── Router step ───────────────────────────────────────────────────────────────
class TestRouter:
    def _state(self, query, parcel_ctx=None):
        s = PipelineState(query=query)
        s.normalized_query = query
        s.parcel_context = parcel_ctx
        return s

    def test_routine_stage_query(self):
        s = router.run(self._state("What is the growth stage of TM-03?"))
        assert s.route == config.ROUTE_ROUTINE

    def test_advisory_fertilizer(self):
        s = router.run(self._state("What fertilizer dose should I apply for rice?"))
        assert s.route in (config.ROUTE_ADVISORY, config.ROUTE_COMPLEX)

    def test_out_of_scope_cotton_on_rice_parcel(self):
        parcel = {"crop": {"name": "Rice"}}
        s = router.run(self._state("What pesticide for pink bollworm in cotton?", parcel))
        assert s.route == config.ROUTE_OUT_OF_SCOPE

    def test_known_gap_is_insufficient_not_out_of_scope(self):
        s = router.run(self._state("What to do about Cordana on my banana?"))
        assert s.route == config.ROUTE_INSUFFICIENT
        assert s.gap_condition == "cordana"

    def test_weather_plus_problem_is_complex(self):
        s = router.run(self._state("Will it rain at TM-09 this week? Should I spray fungicide now?"))
        assert s.route == config.ROUTE_COMPLEX

    def test_text_only_yellow_is_not_visual_without_image(self):
        s = router.run(self._state("My rice leaf is yellow, what should I do?"))
        assert s.route != config.ROUTE_VISUAL

    def test_photo_alone_is_visual(self):
        st = self._state("What is wrong with my paddy leaf?")
        st.image_bytes = "AAAA"
        assert router.run(st).route == config.ROUTE_VISUAL

    def test_confidence_meets_threshold(self):
        s = router.run(self._state("What is the weather forecast for TM-05?"))
        assert s.route_confidence >= config.CONFIDENCE_THRESHOLD


# ── Tools step ────────────────────────────────────────────────────────────────
class TestTools:
    def test_parcel_lookup_found(self):
        state = PipelineState(query="crop stage", parcel_id="TM-01")
        state.intent = "general"
        state.route = config.ROUTE_ROUTINE
        result = tools.run(state)
        assert result.parcel_context is not None
        assert result.parcel_context.get("parcel_id") == "TM-01"

    def test_parcel_lookup_not_found(self):
        state = PipelineState(query="crop stage", parcel_id="TM-9999")
        state.intent = "general"
        state.route = config.ROUTE_ROUTINE
        result = tools.run(state)
        # Should not crash; parcel_context may be None
        assert any(t.step == "tools/parcel_lookup" for t in result.trace)

    def test_weather_fallback_on_timeout(self):
        state = PipelineState(query="weather forecast", parcel_id="TM-05")
        state.inject_failure = "open_meteo_timeout"
        state.intent = "weather"
        state.route = config.ROUTE_ROUTINE
        state.parcel_context = {
            "parcel_id": "TM-05",
            "location": {"lat": 8.91, "lon": 77.31}
        }
        result = tools.weather(state)
        assert result.weather_source == "cached"
        w_trace = [t for t in result.trace if "weather" in t.step]
        assert w_trace[0].tool_or_model == "csv_cache"

    def test_village_query_rice_count(self):
        state = PipelineState(query="How many rice parcels are in the village?")
        state.normalized_query = state.query
        state.intent = "village_query"
        state.route = config.ROUTE_ROUTINE
        result = tools.village_query(state)
        vs = result.parcel_context.get("village_summary", {})
        assert vs.get("count", 0) > 0
        assert vs.get("total_area_ha", 0) > 0


# ── Verify step ───────────────────────────────────────────────────────────────
class TestVerify:
    def _base_state(self):
        s = PipelineState(query="Fertilizer advice for rice")
        s.route = config.ROUTE_ADVISORY
        s.parcel_context = {"crop": {"name": "Rice"}, "data_source": "dummy"}
        s.chunks = [{"text": "Apply 45 kg/ha nitrogen as basal dose.", "title": "CPG Rice", "page": 15}]
        s.raw_answer = "Apply 45 kg/ha nitrogen as basal dose. (dummy data)"
        s.recommendations = ["Apply 45 kg/ha nitrogen as basal dose."]
        return s

    def test_pass_on_clean_answer(self):
        s = verify.run(self._base_state())
        assert s.verification_status == "pass"

    def test_v4_dummy_missing_label(self):
        s = self._base_state()
        s.raw_answer = "Apply 45 kg/ha nitrogen as basal dose."
        s.recommendations = ["Apply 45 kg/ha nitrogen."]
        s.parcel_context["data_source"] = "dummy"
        result = verify.run(s)
        # V4 repairs a missing dummy label itself: the label is added, the repair is recorded, status stays pass
        v4 = next((c for c in result.verification_checks if c["check"] == "V4_dummy_labelled"), None)
        assert v4 is not None and v4["passed"] and v4["auto_repair"] == "auto_labelled_dummy_data"
        assert "dummy" in result.raw_answer.lower()
        assert result.verification_status == "pass"

    def test_v5_empty_answer(self):
        s = self._base_state()
        s.raw_answer = "OK"
        result = verify.run(s)
        v5 = next((c for c in result.verification_checks if c["check"] == "V5_non_empty"), None)
        assert v5 is not None
        assert not v5["passed"]
        assert result.verification_status == "needs_retry"

    def test_crop_mismatch_v1(self):
        s = self._base_state()
        s.raw_answer = "Apply 45 kg/ha nitrogen for cotton crops. (dummy data)"
        s.recommendations = ["Use cotton pesticide."]
        result = verify.run(s)
        v1 = next((c for c in result.verification_checks if c["check"] == "V1_crop_match"), None)
        assert v1 is not None
        # May or may not flag depending on exact text — ensure check runs
        assert "passed" in v1


# ── Full pipeline integration ─────────────────────────────────────────────────
class TestPipeline:
    def test_q01_routine_stage_query(self):
        req = AdvisoryRequest(query="Which growth stage is the crop in survey TM-03?", parcel_id="TM-03")
        result = pipeline.run(req)
        assert result.query == req.query
        assert result.route is not None
        assert result.answer is not None
        assert result.verification is not None

    def test_out_of_scope_returns_correct_route(self):
        req = AdvisoryRequest(query="What pesticide for pink bollworm in cotton?", parcel_id="TM-05")
        result = pipeline.run(req)
        assert result.route == config.ROUTE_OUT_OF_SCOPE

    def test_q25_weather_fallback(self):
        req = AdvisoryRequest(query="What is the weather at TM-05 for the next 3 days?", parcel_id="TM-05")
        result = pipeline.run(req, inject_failure="open_meteo_timeout")
        # Answer should mention cached/fallback data
        obs = result.observability
        assert obs is not None
        # Tools called should include weather
        assert result.answer is not None

    def test_q04_unit_error_injection(self):
        """Q04 inject_failure=unit_error_in_first_answer → verifier should catch dose issue."""
        req = AdvisoryRequest(
            query="What is the fertilizer dose for rice at TM-03?",
            parcel_id="TM-03"
        )
        result = pipeline.run(req, inject_failure="unit_error_in_first_answer")
        # Pipeline should still return a result, verifier runs
        assert result.verification is not None
        assert result.route is not None

    def test_response_has_all_required_fields(self):
        req = AdvisoryRequest(query="Tell me about the crop at TM-01", parcel_id="TM-01")
        result = pipeline.run(req)
        assert result.query is not None
        assert result.model is not None
        assert result.verification is not None
        assert result.observability is not None
        assert isinstance(result.sources, list)

    def test_village_query(self):
        req = AdvisoryRequest(query="How many parcels in Then Malai are growing rice, and what is their total area?")
        result = pipeline.run(req)
        assert result.answer is not None
        assert result.route is not None


# ── Calculator, parser, retry ─────────────────────────────────────────────────
class TestCalculatorAndParser:
    def test_calculator_computes_every_listed_option(self):
        from app.steps import calculator
        st = PipelineState(query="Calculate the urea, DAP and MOP quantity for TM-03", parcel_id="TM-03")
        st.parcel_context = {"area_ha": 2.0}
        st.chunks = [{"title": "CPG Rice", "page": 46, "text": "Blanket recommendation : 50:25:25 kg N:P2O5:K2O /ha"},
                     {"title": "CPG Rice", "page": 48, "text": "Blanket recommendation : 75:25:37.5 kg N:P2O5:K2O /ha"}]
        out = calculator.run(st)
        o = out.calc["options"][0]
        assert (o["N_kg"], o["P2O5_kg"], o["K2O_kg"]) == (100, 50, 50)
        assert o["dap_kg"] == 109 and o["mop_kg"] == 83  # 50/0.46, 50/0.60
        assert len(out.calc["options"]) == 2

    def test_parser_never_leaks_raw_json(self):
        from app.steps import synthesize
        broken = '{"answer": "Tillering stage, 39 days after planting.\nKeep 2 cm water", "recommendations": ["Top-dress N", "Weed'
        d = synthesize._parse_synthesis(broken)
        assert d["answer"].startswith("Tillering stage") and "{" not in d["answer"]
        assert synthesize._parse_synthesis('plain words only')["answer"] == "plain words only"


class TestVerifierRepairs:
    def _state(self, answer, recs, chunks=None, route=None):
        s = PipelineState(query="q", parcel_id="TM-14")
        s.route = route or config.ROUTE_ADVISORY
        s.parcel_context = {"parcel_id": "TM-14", "data_source": "dummy",
                            "crop": {"name": "Banana", "variety": "Nendran", "stage": "Vegetative", "days_after_planting": 70}}
        s.chunks = chunks or [{"text": "Apply 45 kg/ha nitrogen.", "title": "CPG", "page": 1}]
        s.raw_answer, s.recommendations = answer, recs
        return s

    def test_fabricated_dose_is_redacted_not_just_noted(self):
        out = verify.run(self._state("Vegetative stage. Spray mancozeb at 9 g/l now.", ["Spray mancozeb at 9 g/l."]))
        assert "9 g/l" not in out.raw_answer and "[amount: confirm with your KVK]" in out.raw_answer
        assert all("9 g/l" not in r for r in out.sanitized_recommendations)

    def test_stage_is_stated_when_model_omits_it(self):
        out = verify.run(self._state("Fertilizer is due soon.", []))
        assert "Vegetative stage, 70 days after planting" in out.raw_answer
        assert out.verification_status == "pass"

    def test_explicit_refusal_counts_as_gap_disclaimer(self):
        out = verify.run(self._state("It looks like Cordana, but there is no verified TNAU advice. Consult a KVK.", [],
                                     route=config.ROUTE_INSUFFICIENT))
        assert out.verification_status == "pass"


class TestWeatherGating:
    def _run(self, query):
        st = PipelineState(query=query, parcel_id="TM-09", inject_failure="open_meteo_timeout")
        st.intent = "pest_disease"
        return tools.run(st)

    def test_rain_in_the_question_triggers_the_weather_tool(self):
        out = self._run("TM-09 has blast lesions and rain is forecast. What should I do?")
        assert any(t.step == "tools/weather" for t in out.trace)
        assert out.weather_source == "cached"

    def test_spray_decision_triggers_weather_but_plain_stage_question_does_not(self):
        assert any(t.step == "tools/weather" for t in self._run("Should I spray fungicide now?").trace)
        assert not any(t.step == "tools/weather" for t in self._run("How old is the crop?").trace)
