"""The media planner may only choose from Cropsy's closed menu (offline: the model is mocked)."""
import re

import pytest

from app import config, media


@pytest.fixture(autouse=True)
def _no_network_images(monkeypatch):
    monkeypatch.setenv("CROPSY_EXTERNAL_IMAGES", "0")          # tests never reach out to Wikimedia


def test_model_choices_outside_the_menu_are_dropped(monkeypatch):
    monkeypatch.setattr("app.models.bedrock.invoke_text", lambda *a, **k: ('{"diagram": "alien_map", "photo": "not_a_photo", "weather_chart": true, "video": true, "video_query": "http://evil.example/x drip"}', 0, 0))
    p = media.plan("tell me something about yield", "answer")
    assert p["diagram"] is None and p["photo"] is None and p["video"] is True
    assert "http" not in p["video_query"] and "/" not in p["video_query"]


def test_valid_choices_are_kept_and_photo_has_a_credit(monkeypatch):
    monkeypatch.setattr("app.models.bedrock.invoke_text", lambda *a, **k: ('{"diagram": "drip", "photo": "k_drip1", "weather_chart": false, "video": false, "video_query": ""}', 0, 0))
    p = media.plan("drip irrigation for banana", "a")
    assert p["diagram"] == "drip" and p["photo"]["credit"] and p["photo"]["label"]


def test_model_failure_falls_back_to_rules(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.models.bedrock.invoke_text", boom)
    assert media.plan("What does soil pH 8.4 mean?", "x")["diagram"] == "ph_scale"
    assert media.plan("hello", "hi")["diagram"] is None


def test_every_offered_photo_exists_and_is_credited():
    for pid in media.PHOTOS:
        it = media.photo_item(pid)
        assert it and (config.DATA_DIR / "images" / it["url"].replace("/images/", "", 1)).exists() and it["credit"]


def test_a_diagram_must_match_the_question(monkeypatch):           # the model picked the vermicompost bed for an organic-farming question
    monkeypatch.setattr("app.models.bedrock.invoke_text", lambda *a, **k: ('{"diagram": "compost_bed", "photo": null, "weather_chart": false, "video": false, "video_query": ""}', 0, 0))
    assert media.plan("what is organic farming", "a")["diagram"] is None
    assert media.plan("how to make vermicompost", "a")["diagram"] == "compost_bed"


def test_rules_add_a_clear_match_the_model_skipped(monkeypatch):
    monkeypatch.setattr("app.models.bedrock.invoke_text", lambda *a, **k: ('{"diagram": null, "photo": null, "weather_chart": false, "video": false, "video_query": ""}', 0, 0))
    p = media.plan("urea dose for rice", "a")
    assert p["diagram"] == "npk" and p["photo"]["id"] == "urea"


def test_document_values_are_read_exactly_and_not_invented():
    t = "SOIL TEST REPORT Survey 45/2\nParameter Value Rating\npH 8.4 Alkaline\nNitrogen (kg/ha) 180 Low\nPhosphorus 12 kg/ha Medium\nEC 0.4 dS/m Normal"
    rows = media.doc_values(t)
    assert [(r["name"], r["value"]) for r in rows] == [("pH", "8.4"), ("Nitrogen (kg/ha)", "180"), ("Phosphorus", "12"), ("EC", "0.4")]
    assert rows[1]["rating"] == "low" and rows[3]["unit"] == "dS/m"
    assert media.doc_values("a letter about land with one number 5") == []


def test_pest_photos_are_credited_and_labelled_honestly():
    it = media.photo_item("cane_borer_moth")
    assert it and "Public domain" in it["credit"] and "American species" in it["label"]
    assert media.photo_item("bph") is None                        # a photo that was rejected is not offered


def test_table_cells_on_separate_lines_are_read_too():            # Textract returns a PDF table this way
    t = "[page 1] SOIL TEST REPORT\nParameter\nValue\nRating\npH\n8.4\nAlkaline\nNitrogen (kg/ha) 180\nLow\nPhosphorus\n12\nMedium\nPotash\n210\nHigh"
    assert [(r["name"], r["value"], r["rating"]) for r in media.doc_values(t)] == [("pH", "8.4", "alkaline"), ("Nitrogen (kg/ha)", "180", "low"), ("Phosphorus", "12", "medium"), ("Potash", "210", "high")]


def test_library_photos_match_the_pest_or_practice_not_just_the_crop():
    ids = lambda q, c=None: [p["id"] for p in media.library_photos(q, c)]
    assert ids("how to control fall armyworm in maize", "Maize") == ["fall_armyworm_1", "fall_armyworm_2"]
    assert ids("tomato whitefly", "Tomato") == []                  # a tomato-leaf photo is not a whitefly photo
    assert ids("what does a ragi crop look like", "Ragi")[0].startswith("ragi")
    assert ids("hello") == []
    assert all(p["credit"] and "Wikimedia" in p["credit"] for p in media.library_photos("panama wilt in banana", "Banana"))


def test_library_catalog_is_reviewed_licensed_and_on_disk():
    cat = media._library()
    assert len(cat) >= 60
    for it in cat.values():
        assert it["reviewed"] and (config.DATA_DIR / "images" / it["file"]).exists()
        assert re.match(r"^(CC0|Public domain|CC BY)", it["license"], re.I) and "NC" not in it["license"] and it["author"] and it["page"].startswith("https://commons.wikimedia.org/")


def test_videos_are_real_tnau_tv_entries_and_fit_the_question():
    vids = media._videos()
    assert len(vids) >= 100 and all(v["url"] == f"https://www.youtube.com/watch?v={v['id']}" and any(k in v["channel"].lower() for k in ("tnau", "indian council of agricultural research")) for v in vids)
    t = lambda q, c=None: [v["title"] for v in media.tnau_videos(q, c)]
    assert any("Vermicompost" in x for x in t("how to make vermicompost"))
    assert any("Sugarcane" in x and "Pest" in x for x in t("sugarcane pest and disease control", "Sugarcane"))
    assert t("how to control fall armyworm in maize", "Maize") == []            # no armyworm video: a maize-variety video is not shown instead
    assert t("hello") == []


def test_external_search_is_off_when_disabled(monkeypatch):
    monkeypatch.setenv("CROPSY_EXTERNAL_IMAGES", "0")
    assert media.external_photo("rice stem borer damage", "Rice") is None


def test_model_photo_not_named_in_the_question_is_dropped(monkeypatch):
    monkeypatch.setattr("app.models.bedrock.invoke_text", lambda *a, **k: ('{"diagram": null, "photo": "whitefly", "weather_chart": false, "video": false, "video_query": ""}', 0, 0))
    assert media.plan("sugarcane pest and disease control", "a", "Sugarcane")["photo"] is None
    assert media.plan("how to control whitefly in tomato", "a", "Tomato")["photo"]["id"] == "whitefly"


def test_new_diagram_rules():
    d = lambda q: media._rules(q, "")["diagram"]
    assert d("what are the leaf symptoms of potassium deficiency") == "deficiency_table"
    assert d("life cycle of fall armyworm") == "insect_cycle" and d("parts of a plant") == "plant_parts"
    assert d("soil pH 8") == "ph_scale" and d("urea dose for rice") == "npk" and d("hello") is None
