"""Language-understanding regression cases (offline): the farmer's own words decide the crop and the topic, whatever the model's English rewrite says."""
import pytest

from app.steps import understand


@pytest.mark.parametrize("text,crop", [
    ("nel ku uram evlo podanum", "Rice"), ("paddy blast control", "Rice"), ("நெல் பயிருக்கு உரம்", "Rice"),
    ("ulundhu pooch marundhu", "Blackgram"), ("உளுந்து பூச்சி மருந்து", "Blackgram"), ("black gram seed rate", "Blackgram"),
    ("kambu vithai alavu", "Cumbu"), ("கம்பு விதை அளவு", "Cumbu"), ("pearl millet spacing", "Cumbu"), ("bajra sowing time", "Cumbu"),
    ("ragi blast spray", "Ragi"), ("கேழ்வரகு நோய்", "Ragi"), ("finger millet seed rate", "Ragi"),
    ("cholam stem borer", "Sorghum"), ("சோளம் விதை", "Sorghum"), ("makkacholam fall armyworm", "Maize"),
    ("ellu sowing time", "Sesame"), ("gingelly seed rate", "Sesame"), ("avanakku pest", "Castor"), ("sooriyakanthi vithai", "Sunflower"),
    ("soya bean sowing", "Soybean"), ("bengal gram wilt", "Bengalgram"), ("kadalai vithai", "Groundnut"),   # ambiguous in Tamil (groundnut or chickpea); the common meaning is used and the answer names the crop it assumed
    
    ("manjal ilai yellow aaguthu", None), ("turmeric rhizome rot", "Turmeric"), ("மஞ்சள் கிழங்கு அழுகல்", "Turmeric"),
    ("wheat seed rate", "Wheat"), ("gothumai vithai", "Wheat"), ("what fertilizer", None), ("hello", None),
])
def test_crop_comes_from_the_farmers_words(text, crop):
    assert understand._crop_from_words(text) == crop


@pytest.mark.parametrize("text,topic", [
    ("uram evlo podanum", "fertilizer"), ("nel ku eppo uram podanum", "fertilizer"), ("நெல்லுக்கு உரம் எவ்வளவு", "fertilizer"),
    ("ulundhu pooch marundhu", "pest"), ("poochi kolli marundhu", "pest"), ("மிளகாய் பூச்சி மருந்து", "pest"),
    ("tomato ku enna marundhu adikkanum", "spray"), ("நோய் மருந்து", "disease"), ("vithai alavu evlo", "seed"),
    ("kalai edukka", "weed"), ("aruvadai eppo", "harvest"),
])
def test_topic_word_is_found(text, topic):
    assert understand._topic_from_words(text)[0] == topic


@pytest.mark.parametrize("text", ["how to control sheath blight in rice", "what is the sowing time for wheat", "groundnut leaf spot", "TM-05 irrigation"])
def test_plain_english_questions_get_no_forced_topic(text):
    assert understand._topic_from_words(text) is None


@pytest.mark.parametrize("text,follow", [
    ("and the seed rate?", True), ("what about its spacing", True), ("athu evlo podanum", True), ("appo vithai alavu?", True), ("இதற்கு அளவு என்ன", True),
    ("wheat seed rate", False), ("PM Kisan eligibility", False), ("rice blast control", False), ("what is the weather in Tenkasi today and tomorrow evening", False),
])
def test_follow_up_only_when_the_question_depends_on_the_last_answer(text, follow):
    assert understand._is_followup(text) is follow
