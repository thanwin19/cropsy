"""Advisory dashboard maths and rules (no network). Corpus-based checks use the real TNAU chunks."""
from app import advisory_extras as ex
from app.steps import tools

tools._load_parcels()


def _p(pid):
    return tools._PARCEL_BY_ID[pid]


def test_soil_test_ratings_and_dose_adjustment():
    ev = ex.evaluate_soil_test({"N": 250, "P": 18, "K": 300, "OC": 0.4, "pH": 5.2, "EC": 3.1})
    assert [ev["ratings"][k]["rating"] for k in "NPK"] == ["low", "medium", "high"]
    assert ev["adjustment"] == {"N": 1.25, "P": 1.0, "K": 0.75}
    assert ev["counts"] == {"needs_attention": 1, "monitor": 1, "optimal": 1}
    assert ev["ph"]["class"] == "Strongly acidic" and ev["salinity"]["class"] == "Very slightly saline"
    assert ev["ratings"]["OC"]["rating"] == "low"


def test_salinity_classes_follow_usda_handbook_60():
    assert [ex.classify_ec(v)["class"] for v in (1, 3, 6, 12, 20)] == [
        "Non-saline", "Very slightly saline", "Slightly saline", "Moderately saline", "Strongly saline"]


def test_irrigation_uses_method_efficiency_and_pump_rate():
    water = {"days": [{"date": "2026-10-03", "irrigation_mm": 6.0, "et0_mm": 5, "etc_mm": 6, "rain_mm": 0}]}
    parcel = {"crop": {"name": "Banana"}, "area_ha": 2.0}
    drip = ex.irrigation_plan(parcel, water, "drip", 10)["days"][0]
    spr = ex.irrigation_plan(parcel, water, "sprinkler", 10)["days"][0]
    assert drip["gross_mm"] == 6.7 and spr["gross_mm"] == 8.0
    assert drip["volume_m3"] == round(6.7 * 10 * 2) and drip["pump_hours"] == round(drip["volume_m3"] * 1000 / (10 * 3600), 1)
    assert ex.irrigation_plan({"crop": {"name": "Rice"}, "area_ha": 1}, water, "drip", 8)["method"] == "flood"   # paddy is always flooded


def test_plant_estimate_uses_curated_tnau_density_and_is_variety_aware():
    c = ex.plant_estimate({"crop": {"name": "Coconut"}, "area_ha": 2.0})
    assert c["plants_at_spacing"] == 350 and c["plants_usable"] == 315
    nendran = ex.plant_estimate({"crop": {"name": "Banana", "variety": "Nendran"}, "area_ha": 1.0})
    grand = ex.plant_estimate({"crop": {"name": "Banana", "variety": "Grand Naine"}, "area_ha": 1.0})
    assert nendran["per_ha"] == 5000 and grand["per_ha"] == 4600
    assert ex.plant_estimate({"crop": {"name": "Sugarcane"}, "area_ha": 1.0})["available"] is False


def test_controls_come_from_curated_passages_and_tungro_never_gets_a_fungicide():
    watch = ex.pest_watch(_p("TM-09"))                      # a rice parcel with recorded blast
    by = {i["code"]: i for i in watch["watchlist"]}
    assert watch["watchlist"][0]["code"] == "rice_blast" and watch["watchlist"][0]["recorded_on_parcel"]
    blast = " ".join(c["text"] for g in ("cultural", "organic", "chemical") for c in by["rice_blast"][g]).lower()
    assert "carbendazim" in blast and "pseudomonas" in blast
    for item in watch["watchlist"]:
        for g in ("cultural", "organic", "chemical"):
            assert all(c["source"] and " p." in c["source"] for c in item[g])      # every passage cites its page
    if "rice_tungro" in by:                                  # a virus: vector control only, no fungicide
        assert not by["rice_tungro"]["chemical"]


def test_recorded_issue_without_advice_is_reported():
    w = ex.pest_watch(_p("TM-12"))                          # recorded: coconut gray leaf spot (not named in the guides)
    assert w["recorded_without_advice"] is None or w["recorded_without_advice"] == "Gray leaf spot"
    assert isinstance(w["watchlist"], list)


def test_analysis_scale_shares_add_up_to_the_whole_parcel():
    v = ex.vigour_classes("TM-09")
    assert v and abs(sum(c["share"] for c in v["classes"]) - 1.0) < 0.02
    assert {c["name"] for c in v["classes"]} >= {"Good crop health & irrigation", "No clear view"}


def test_yield_outlook_is_the_range_of_the_last_three_seasons():
    y = ex.yield_outlook(_p("TM-09"))
    last3 = [s["yield"] for s in y["last_seasons"][-3:]]
    assert y["expected_low"] == round(min(last3), 1) and y["expected_high"] == round(max(last3), 1)


def test_the_whole_report_builds_for_every_crop():
    """Catches a missing helper or a broken section for any crop (a NameError reached the live API once)."""
    from app import field_report as fr
    seen = set()
    for p in tools._PARCELS:
        crop = p["crop"]["name"]
        if crop in seen:
            continue
        seen.add(crop)
        rep = fr.build(p["parcel_id"])
        for key in ("instruction", "vigour", "irrigation", "soil_panel", "yield_outlook", "plants", "watch", "fertilizer", "health", "water", "harvest"):
            assert key in rep, (crop, key)
    assert seen == {"Rice", "Banana", "Sugarcane", "Maize", "Coconut", "Groundnut", "Cotton", "Blackgram", "Chilli", "Turmeric"}


def test_weed_controls_are_curated_and_banana_has_none():
    rice = ex.pest_watch(_p("TM-09"))
    assert rice["weeds"]["chemical"] and all(" p." in c["source"] for c in rice["weeds"]["chemical"])
    banana = ex.pest_watch(next(p for p in tools._PARCELS if p["crop"]["name"] == "Banana"))
    assert not banana["weeds"]["chemical"] and not banana["weeds"]["organic"] and banana["weeds_note"]
