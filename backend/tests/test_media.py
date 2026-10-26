"""Reference photos shown with an answer must match the problem asked about and must exist on disk (offline)."""
from app import config
from app.schemas import PipelineState
from app.steps import refphotos


def _photos(q, crop=None):
    s = PipelineState(query=q, crop_hint=crop)
    return refphotos.reference_photos(s)


def test_named_disease_gets_its_own_photos():
    p = _photos("banana sigatoka control", "Banana")
    assert p and all("Sigatoka" in x["condition"] for x in p)
    p = _photos("red rot in sugarcane", "Sugarcane")
    assert p and all("Red rot" in x["condition"] for x in p)


def test_ambiguous_word_without_a_crop_shows_nothing():          # "rust" is groundnut rust and sugarcane rust: no guess
    assert _photos("how to control rust") == []
    assert _photos("groundnut rust", "Groundnut") and not _photos("rust", "Rice")


def test_a_question_with_no_photographed_problem_shows_none():   # no stem borer photos exist: none is invented
    assert _photos("how to control stem borer in sugarcane", "Sugarcane") == []


def test_every_photo_file_exists():
    for q, c in (("banana sigatoka", "Banana"), ("red rot", "Sugarcane"), ("groundnut rust", "Groundnut"), ("rice blast", "Rice")):
        for p in _photos(q, c):
            assert (config.DATA_DIR / "images" / p["url"].replace("/images/", "", 1)).exists(), p["url"]


def test_comparison_question_gets_photos_of_both_conditions():
    p = _photos("what is the difference between rice blast and sheath blight", "Rice")
    assert {x["condition"] for x in p} == {"Rice blast", "Sheath blight"} and len(p) == 4
