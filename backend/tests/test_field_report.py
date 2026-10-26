"""Field report maths and alert rules (no network, no Bedrock)."""
from app import field_report as fr


def _rice(zone="terrace", **over):
    p = {"parcel_id": "TM-X", "zone": zone, "area_ha": 2.0,
         "crop": {"name": "Rice", "stage": "Panicle Initiation", "planting_date": "2026-08-10"},
         "terrain": {"waterlogging_susceptibility": "low"},
         "management": {"days_since_last_irrigation": 2}, "observed_issue": {"code": "healthy"}}
    p.update(over)
    return p


FC = [{"date": f"2026-10-0{i}", "rain_mm": 0.0, "et0_mm": 5.0, "tmax_c": 32, "tmin_c": 24} for i in range(1, 8)]


def test_water_plan_is_kc_times_et0_minus_effective_rain():
    plan = fr.water_plan(_rice(), FC, "live")
    assert plan["crop_coefficient"] == 1.2 and plan["days"][0]["irrigation_mm"] == 6.0
    wet = [dict(d, rain_mm=10.0) for d in FC]            # 80% of 10 mm = 8 mm > 6 mm crop use
    assert fr.water_plan(_rice(), wet, "live")["total_mm_7d"] == 0.0
    assert plan["total_m3_per_ha_7d"] == round(plan["total_mm_7d"] * 10)   # 1 mm on 1 ha = 10 m3


def test_harvest_window_comes_from_the_stage_calendar():
    w = fr.harvest_window(_rice())
    assert w["available"] and w["window_start"] == "2026-11-19" and w["window_end"] == "2026-12-18"
    assert not fr.harvest_window(_rice(crop={"name": "Coconut", "stage": "x", "planting_date": "2019-01-01"}))["available"]


def test_heavy_rain_alert_only_above_threshold_and_ranks_valley_non_rice_high():
    rainy = [dict(d, rain_mm=15.0) for d in FC]
    banana = _rice("valley", crop={"name": "Banana", "stage": "Vegetative", "planting_date": "2026-05-01"})
    types = {a["type"]: a for a in fr.alerts_for(banana, rainy, "live")}
    assert types["heavy_rain"]["severity"] == "high"
    assert "heavy_rain" not in {a["type"] for a in fr.alerts_for(banana, FC, "live")}


def test_satellite_stress_is_high_watch_is_medium_and_dummy_records_rank_low():
    sat = {"status": "stress", "latest_ndvi": 0.4, "latest_date": "2026-09-29", "baseline_ndvi": 0.55, "change": -0.15}
    a = fr.alerts_for(_rice(), FC, "live", sat)
    assert a[0]["type"] == "crop_stress" and a[0]["severity"] == "high"
    assert fr.alerts_for(_rice(), FC, "live", dict(sat, status="watch", change=-0.06))[0]["severity"] == "medium"
    rec = fr.alerts_for(_rice(observed_issue={"code": "rice_blast", "label": "Rice blast", "severity": "moderate", "since_days": 3}), FC, "live")
    assert rec[0]["type"] == "recorded_issue" and rec[0]["severity"] == "low"


def test_fertilizer_options_scale_with_area_and_cite_a_page():
    out = fr.fertilizer_options({"area_ha": 2.0, "crop": {"name": "Rice"}})
    assert out["options"], "TNAU rice chunks should yield at least one kg/ha NPK recommendation"
    o = out["options"][0]
    assert o["source"] and o["N_kg"] > 0 and o["urea_kg"] > 0


def test_one_clear_instruction_is_built_from_rules():
    sat = {"status": "stress", "latest_ndvi": 0.4, "latest_date": "2026-09-29", "baseline_ndvi": 0.55, "change": -0.15}
    banana = {"parcel_id": "TM-X", "zone": "terrace", "area_ha": 2.0, "terrain": {}, "management": {"days_since_last_irrigation": 1},
              "crop": {"name": "Banana", "stage": "Vegetative", "planting_date": "2026-05-01"}, "observed_issue": {"code": "healthy"}}
    water = fr.water_plan(banana, FC, "live")
    alerts = fr.alerts_for(banana, FC, "live", sat)
    ins = fr.instruction(banana, water, alerts, FC)
    assert "Inspect this field" in ins["headline"]
    assert 1 <= len(ins["steps"]) <= 3 and any("Irrigate about" in x for x in ins["steps"])
    calm = fr.instruction(banana, water, [], [dict(d, rain_mm=0.0) for d in FC])
    assert calm["headline"].startswith("Field looks steady")


def test_village_brief_counts_fields_that_need_action(monkeypatch):
    alerts = [{"parcel_id": "A", "type": "crop_stress", "severity": "high"}, {"parcel_id": "B", "type": "crop_stress", "severity": "medium"},
              {"parcel_id": "C", "type": "irrigation_due", "severity": "medium"}, {"parcel_id": "A", "type": "irrigation_due", "severity": "medium"}]
    monkeypatch.setattr(fr, "all_alerts", lambda min_severity="low": {"alerts": alerts, "forecast_source": "live", "count": 4, "by_type": {}})
    monkeypatch.setattr(fr.tools, "_PARCELS", [{}] * 10)
    b = fr.village_brief()
    assert b["headline"] == "2 of 10 fields need action this week."      # A and C (B is only a watch)
    assert b["counts"]["stress"] == 1 and b["counts"]["watch"] == 1 and any("Inspect first: A" in x for x in b["steps"])
