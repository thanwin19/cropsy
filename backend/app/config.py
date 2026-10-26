"""
config.py — Cropsy backend configuration.
All model IDs, paths, thresholds in one place. Steps import from here only.
"""
from __future__ import annotations

import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
CACHE_DIR = BASE_DIR / "cache"
UPLOAD_DIR = (Path("/tmp") / "uploads") if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else BASE_DIR / "uploads"   # Lambda's code folder is read-only

PARCELS_FILE = DATA_DIR / "parcels.json"
QUERIES_FILE = DATA_DIR / "queries.json"
WEATHER_FILE = DATA_DIR / "weather" / "daily.csv"
SATELLITE_SUMMARY_FILE = DATA_DIR / "satellite" / "ndvi_summary.json"
CHUNKS_FILE = KNOWLEDGE_DIR / "chunks.jsonl"
SOURCES_FILE = KNOWLEDGE_DIR / "sources.json"
IMAGE_MANIFEST_FILE = DATA_DIR / "images" / "manifest.json"

EMBED_CACHE_FILE = CACHE_DIR / "embeddings.npz"
IMAGE_EMBED_CACHE_FILE = CACHE_DIR / "image_embeddings.npz"
MODEL_STATUS_FILE = CACHE_DIR / "model_status.json"

# ── AWS ───────────────────────────────────────────────────────────────────────
AWS_PROFILE = os.getenv("AWS_PROFILE", "FAI-TCE-Team36-Builder-Textract-402365884845")   # covers Bedrock, Textract and Transcribe (old: FAI-TCE-Builder-AI-402365884845, no Textract or Transcribe)
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# ── Model IDs ─────────────────────────────────────────────────────────────────
# Bedrock model IDs — ap-south-1
MODEL_NOVA_MICRO = "apac.amazon.nova-micro-v1:0"
MODEL_NOVA_LITE = "apac.amazon.nova-lite-v1:0"
MODEL_MINISTRAL_3B = "mistral.ministral-3-3b-instruct"
MODEL_MINISTRAL_8B = "mistral.ministral-3-8b-instruct"
MODEL_TITAN_TEXT = "amazon.titan-embed-text-v2:0"
MODEL_TITAN_MULTIMODAL = "amazon.titan-embed-image-v1"  # NOT ":0": the :0 ARN is denied for this account

# Tier labels
TIER_CHEAP_OPEN = "cheap_open"
TIER_MID = "mid"
TIER_SMART = "smart"
TIER_VISION = "vision"

# ── Cost table (USD per 1K tokens, approximate) ───────────────────────────────
COST_PER_1K: dict[str, float] = {
    MODEL_NOVA_MICRO: 0.000035,
    MODEL_NOVA_LITE: 0.00006,
    MODEL_MINISTRAL_3B: 0.00004,
    MODEL_MINISTRAL_8B: 0.00010,
    MODEL_TITAN_TEXT: 0.00002,        # per 1K tokens embedding
    MODEL_TITAN_MULTIMODAL: 0.00006,  # per image
}

# ── Routing thresholds ────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.85

# Route labels
ROUTE_ROUTINE = "ROUTINE"
ROUTE_ADVISORY = "ADVISORY"
ROUTE_VISUAL = "VISUAL"
ROUTE_COMPLEX = "COMPLEX"
ROUTE_OUT_OF_SCOPE = "OUT_OF_SCOPE"   # crop/topic outside the corpus
ROUTE_INSUFFICIENT = "INSUFFICIENT"   # in scope, but the corpus has no verified advice (known evidence gap)

# ── Pipeline settings ─────────────────────────────────────────────────────────
MAX_CHUNKS = 5                    # RAG top-k
MAX_IMAGE_MATCHES = 3             # multimodal top-k
BEDROCK_TIMEOUT = 30              # seconds per call
BEDROCK_MAX_RETRIES = 3
BEDROCK_RETRY_DELAY = 1.5         # seconds, multiplied by attempt

# Weather live API
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT = 8            # seconds

# ── Safety / verifier ─────────────────────────────────────────────────────────
# Crops that have insufficient evidence in our KB — must say so
# (sugarcane mosaic and coconut leaf rot were gaps until the TNAU portal pages were added to the corpus)
KNOWN_GAPS = {
    "cordana",
    "pestalotiopsis",
    "maize gray leaf spot",
    "maize grey leaf spot",
}
# Issue codes (photo classes) whose photo can be recognised but for which no verified advice exists
# Local and alternative names -> the crop name used in the knowledge base
CROP_ALIASES = {
    "paddy": "rice", "nellu": "rice", "arisi": "rice", "thennai": "coconut", "maakkacholam": "maize", "kamba": "sugarcane",
    "peanut": "groundnut", "groundnuts": "groundnut", "verkadalai": "groundnut", "nilakadalai": "groundnut", "manilakottai": "groundnut",
    "paruthi": "cotton", "panju": "cotton",
    "chili": "chilli", "chillies": "chilli", "chilies": "chilli", "mulagai": "chilli", "milagai": "chilli",
    "cholam": "sorghum", "jowar": "sorghum", "sorghum": "sorghum", "pearl millet": "cumbu", "bajra": "cumbu", "kambu": "cumbu", "finger millet": "ragi", "kezhvaragu": "ragi", "kelvaragu": "ragi", "keppai": "ragi",
    "godhumai": "wheat", "mulakai": "chilli", "mulagai": "chilli", "milakai": "chilli", "mirchi": "chilli", "gothumai": "wheat", "godumai": "wheat", "kothumai": "wheat", "கோதுமை": "wheat", "makkacholam": "maize", "makka cholam": "maize", "makkachola": "maize", "pigeon pea": "redgram", "pigeonpea": "redgram", "toor": "redgram", "tur": "redgram", "thuvarai": "redgram", "red gram": "redgram", "green gram": "greengram", "moong": "greengram",
    "pachai payaru": "greengram", "pasi payaru": "greengram", "cow pea": "cowpea", "thattai payaru": "cowpea", "horse gram": "horsegram", "kollu": "horsegram", "bengal gram": "bengalgram", "chickpea": "bengalgram",
    "chana": "bengalgram", "kondakadalai": "bengalgram", "gingelly": "sesame", "til": "sesame", "ellu": "sesame", "soya": "soybean", "soya bean": "soybean", "avanakku": "castor", "aamanakku": "castor", "sooriyakanthi": "sunflower", "suryamukhi": "sunflower",
    "thakkali": "tomato", "takkali": "tomato", "thakali": "tomato", "தக்காளி": "tomato", "nel": "rice", "kadalai": "groundnut", "karumbu": "sugarcane", "vazhai": "banana", "ulundhu": "blackgram", "urad": "blackgram", "black gram": "blackgram", "ulundu": "blackgram", "ulutham paruppu": "blackgram",
    "manjal": "turmeric", "haldi": "turmeric",
    # Tamil script names
    "நெல்": "rice", "எள்ளு": "sesame", "ஆமணக்கு": "castor", "சூரியகாந்தி": "sunflower", "சோயா": "soybean", "கம்பு": "cumbu", "கேழ்வரகு": "ragi", "கோதுமை": "wheat", "துவரை": "redgram", "பச்சைப்பயறு": "greengram", "தட்டைப்பயறு": "cowpea", "கொள்ளு": "horsegram", "கொண்டைக்கடலை": "bengalgram", "சோளம்": "sorghum", "அரிசி": "rice", "மக்காச்சோளம்": "maize", "கரும்பு": "sugarcane", "தென்னை": "coconut", "வாழை": "banana",
    "நிலக்கடலை": "groundnut", "வேர்க்கடலை": "groundnut", "பருத்தி": "cotton", "உளுந்து": "blackgram", "மிளகாய்": "chilli", "மஞ்சள்": "turmeric",
}
CROPS = ["Rice", "Maize", "Sugarcane", "Coconut", "Banana", "Groundnut", "Cotton", "Blackgram", "Chilli", "Turmeric", "Tomato",
         "Sorghum", "Cumbu", "Ragi", "Wheat", "Redgram", "Greengram", "Cowpea", "Horsegram", "Bengalgram", "Soybean", "Sesame", "Castor", "Sunflower"]


def norm_crop(name: str | None) -> str:
    n = (name or "").lower().strip()
    return CROP_ALIASES.get(n, n)


GAP_ISSUE_CODES = {"banana_cordana", "banana_pestalotiopsis", "maize_gray_leaf_spot"}

# Dummy data label — must appear verbatim in answers that touch dummy fields
DUMMY_LABEL = "(dummy data)"

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]
if os.environ.get("CROPSY_CORS_ORIGINS"):          # staging/production: comma-separated https origins of the deployed frontend
    CORS_ORIGINS = CORS_ORIGINS + [o.strip() for o in os.environ["CROPSY_CORS_ORIGINS"].split(",") if o.strip()]
