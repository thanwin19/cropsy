"""The curated TNAU controls table must keep resolving against the corpus, and must never attach the wrong kind of advice."""
import re

from app import controls as c


def test_every_curated_control_resolves_to_verbatim_corpus_text():
    for code, spec in c.CONTROLS.items():
        r = c.controls_for(code)
        assert r["unresolved"] == 0, f"{code}: {r['unresolved']} anchor(s) no longer found in the corpus"
        assert all(it["text"] and it["page"] for it in r["items"]), code


def test_organic_options_resolve_for_every_crop():
    for crop in c.ORGANIC_NUTRIENTS:
        assert c.organic_nutrients(crop), crop


def test_virus_diseases_never_get_a_fungicide():
    # an early automatic extractor attached propiconazole to rice tungro (a virus): the curated table must not
    for code in ("rice_tungro", "cane_yellow_leaf", "cane_mosaic"):
        txt = " ".join(i["text"] for i in c.controls_for(code)["items"]).lower()
        assert not re.search(r"propiconazole|carbendazim|mancozeb|tricyclazole|hexaconazole", txt), code


def test_unlisted_problems_say_so_instead_of_guessing():
    for code in ("banana_cordana", "banana_pestalotiopsis", "maize_gray_leaf_spot", "healthy", None):
        r = c.controls_for(code)
        assert not r["covered"] and not r["items"] and "No verified" in r["note"]


def test_closest_listed_disease_is_declared():
    assert "brown spot" in c.controls_for("rice_narrow_brown_spot")["closest"].lower()


def test_plant_estimates_use_tnau_density_and_never_count_plants():
    assert c.plant_estimate("Coconut", "West Coast Tall", 2.0)["total"] == 350
    assert c.plant_estimate("Banana", "Nendran", 1.0)["total"] == 5000
    assert c.plant_estimate("Banana", "Grand Naine", 1.0)["total"] == 4600
    assert not c.plant_estimate("Sugarcane", "Co 86032", 1.0)["available"]
    assert "cannot count" in c.plant_estimate("Maize", None, 1.0)["note"]


def test_weed_controls_resolve_for_listed_crops_and_banana_says_nothing_verified():
    for crop in ("Rice", "Maize", "Sugarcane", "Coconut"):
        r = c.weed_controls(crop)
        assert r["covered"] and all(i["page"] for i in r["items"]), crop
    b = c.weed_controls("Banana")
    assert not b["covered"] and "No verified" in b["note"]
    assert "Atrazine" in " ".join(i["text"] for i in c.weed_controls("Maize")["items"])


def test_added_crops_controls_all_resolve_to_verbatim_guide_text():
    new = ("Groundnut", "Cotton", "Blackgram", "Chilli", "Turmeric")
    for code, spec in c.CONTROLS.items():
        if spec["crop"] in new:
            r = c.controls_for(code)
            assert r["items"] and not r["unresolved"], code
            assert all(" p." in i["source"] for i in r["items"]), code
    for crop in new:
        assert c.organic_nutrients(crop), crop
        assert c.plant_estimate(crop, None, 1.0)["available"] == (crop != "Cotton")
