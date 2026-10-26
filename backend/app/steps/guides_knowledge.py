"""
guides_knowledge.py: fixed, reviewed "general farm knowledge" cards (schemes, soil sampling, water saving, seasons, pesticide safety, storage,
livestock, marketing), shown with photos. Same rules as guides.py: no language model, no chemical doses, amounts and rates that change
are marked "check the current notice", and every card names its source.
"""
from __future__ import annotations

from urllib.parse import quote_plus


def _videos(*terms: str) -> list[dict]:
    return [{"label": t, "url": "https://www.youtube.com/results?search_query=" + quote_plus(t)} for t in terms]


MYSCHEME = {"title": "myScheme (Government of India): find schemes you are eligible for", "url": "https://www.myscheme.gov.in/"}
PMKISAN = {"title": "PM-KISAN official portal", "url": "https://pmkisan.gov.in/"}
SHC = {"title": "Soil Health Card portal (Department of Agriculture)", "url": "https://soilhealth.dac.gov.in/"}
TNAU = {"title": "TNAU Agritech Portal", "url": "https://agritech.tnau.ac.in/"}
ENAM = {"title": "e-NAM (National Agriculture Market)", "url": "https://enam.gov.in/"}
PMKSY = {"title": "PMKSY (Per Drop More Crop): micro-irrigation", "url": "https://pmksy.gov.in/"}

KNOWLEDGE = {
    "schemes": {
        "title": "Government schemes: money, insurance, loans and subsidies", "kind": "knowledge", "photos": ["k_csc"],
        "steps": [
            "PM-KISAN: income support paid straight to the bank account of an eligible landholding farmer family, currently Rs 6,000 a year in three instalments. Register at the portal or a Common Service Centre and finish e-KYC (Aadhaar linked to the bank account and land record).",
            "Crop insurance (PMFBY): the farmer pays only a small share of the premium and the government pays the rest. Enrol before the cut-off date for the season through your bank, a Common Service Centre or the portal; report any loss within 72 hours.",
            "Kisan Credit Card: a flexible crop loan from a bank or cooperative society at a subsidised interest rate when repaid on time. Take your land record, Aadhaar and passbook.",
            "Drip and sprinkler subsidy (PMKSY, Per Drop More Crop): a share of the cost is paid for micro-irrigation; the share depends on your farm size. Apply through the Horticulture or Agricultural Engineering office.",
            "Solar pumps (PM-KUSUM) and solar fencing: ask the block agriculture office whether a scheme is open in your district.",
            "The Uzhavan app and your block agriculture office show schemes open in Tamil Nadu, with weather and market prices.",
        ],
        "notes": ["Amounts, premium rates and dates change every season: check the current notice on the official portal before you act.",
                  "Never pay anyone to 'get' a scheme for you, and never share an OTP or bank PIN."],
        "warning": None, "source": MYSCHEME, "extra_sources": [PMKISAN],
        "videos": _videos("PM Kisan registration eKYC tamil", "PMFBY crop insurance enrol claim tamil", "Kisan Credit Card apply farmers"),
    },
    "soil_sampling": {
        "title": "How to take a soil sample and use the Soil Health Card", "kind": "knowledge", "photos": ["k_soil1", "k_soil2", "k_soillab"],
        "steps": [
            "Sample before sowing, and not soon after fertilizer or manure has been applied.",
            "Treat each uniform plot separately. Walk in a zigzag and take about 8 to 10 spots; skip bunds, tree shade, manure heaps and wet corners.",
            "At each spot clear the surface litter and dig a V-shaped pit about 15 cm deep for field crops (deeper for trees such as coconut: ask the lab). Cut a thin slice of soil from the side of the pit.",
            "Collect all slices in a clean bucket (never a fertilizer bag), mix well, spread on paper and divide into four; keep opposite quarters and repeat until you have about half a kilo.",
            "Dry it in shade, put it in a clean bag and label it: your name, parcel number, crop, date.",
            "Take it to the nearest soil testing laboratory (agriculture department or TNAU) and ask for the Soil Health Card, which gives the fertilizer advice for your crop.",
            "Repeat every couple of years, and sooner if the crop changes a lot.",
        ],
        "notes": ["A soil test tells you what the soil already holds, so you do not pay for fertilizer the soil does not need."],
        "source": SHC, "extra_sources": [TNAU],
        "videos": _videos("how to collect soil sample for testing tamil", "soil health card how to read"),
    },
    "water_saving": {
        "title": "Saving water: drip, mulch and rice water management", "kind": "knowledge", "photos": ["k_drip1", "k_drip2"],
        "steps": [
            "Drip irrigation gives each plant its water at the root and can carry fertilizer with it (fertigation). It suits banana, coconut, sugarcane, chilli and turmeric well and saves a lot of water compared with flooding.",
            "Flush the drip lines and clean the filters regularly; a blocked dripper means a thirsty plant.",
            "Mulch the soil with straw, dry leaves, coconut husk or crop residue: it cuts evaporation and weeds.",
            "Rice: instead of keeping the field flooded all the time, let the water drop to about 15 cm below the surface (a perforated tube set in the soil shows this), then irrigate again. Keep water on the field around flowering. This is called alternate wetting and drying.",
            "Irrigate early morning or late evening, level the field, mend bunds and channels, and store rain in a farm pond if you can.",
            "Ask about the micro-irrigation subsidy before you buy (see the schemes card).",
        ],
        "notes": ["Water need depends on crop, stage and weather: for amounts, ask Cropsy about your crop and parcel."],
        "source": PMKSY, "extra_sources": [TNAU],
        "videos": _videos("drip irrigation banana farmers tamil", "alternate wetting and drying rice water saving"),
    },
    "season": {
        "title": "Tamil Nadu seasons at a glance", "kind": "knowledge", "photos": ["k_paddy1", "k_paddy2"],
        "steps": [
            "Rice has its own seasons here: Kuruvai (about June to September, short-duration varieties), Samba (about August to January, the main long season), Thaladi (about September or October to January or February) and Navarai (about December to March).",
            "The north-east monsoon (October to December) brings most of Tamil Nadu's rain; the south-west monsoon (June to September) is lighter on most of the plains.",
            "Other crops follow the rain and irrigation: sow groundnut, blackgram, cotton, chilli and maize to suit the season and variety your TNAU or KVK officer recommends.",
            "Exact sowing and planting dates depend on the variety and on the rain that year.",
        ],
        "notes": ["For a crop-specific schedule ask Cropsy, for example 'when to sow groundnut' or 'fertilizer schedule for banana', and it answers from the TNAU documents."],
        "source": TNAU, "videos": _videos("Tamil Nadu cropping seasons kuruvai samba thaladi"),
    },
    "pesticide_safety": {
        "title": "Using pesticides safely", "kind": "knowledge", "photos": ["k_spray"],
        "steps": [
            "Buy only a registered product, in its original sealed container with the label. Ask the KVK or agriculture officer which product and how much for your crop and pest.",
            "Read the label first. Measure with a proper cap or cup; never guess and never mix products on your own.",
            "Mix in the open, wearing gloves, a mask or cloth over nose and mouth, long sleeves and trousers, and boots or covered feet.",
            "Spray with the wind behind you, in the cool of the morning or evening, never in strong wind, heat or just before rain, and never against the wind.",
            "Do not eat, drink or smoke while spraying. Keep children, cattle and pets away from the field.",
            "After spraying, bathe, and wash the clothes separately. Respect the waiting time on the label before harvest and before anyone enters the field.",
            "Wash the sprayer away from ponds, wells and streams. Rinse empty containers three times, puncture them, and never reuse them.",
            "Spray when bees are not working the flowers (evening) to protect pollinators.",
            "Store pesticides locked, away from food, feed and children.",
        ],
        "warning": "Never reuse empty pesticide containers. If anyone feels sick after spraying, ask Cropsy about 'pesticide poisoning' and call 108.",
        "source": TNAU, "videos": _videos("pesticide safety farmers tamil spraying precautions", "safe use of pesticides protective clothing"),
    },
    "storage": {
        "title": "Seed and grain: drying, treatment and storage", "kind": "knowledge", "photos": ["k_bin"],
        "steps": [
            "Dry grain and seed fully before storing. Damp grain heats up, moulds and breeds weevils. Safe moisture is roughly 12 to 14 per cent for cereals and lower for groundnut kernels and pulses: confirm with your KVK.",
            "Clean the store first: sweep, remove old grain and dust, and fix cracks and leaks.",
            "Use clean or new bags, stack them on wooden planks off the floor and a little away from the walls, and keep seed and food grain apart.",
            "Check often for weevils, damp patches and rats; dry again at once if the grain feels warm or smells.",
            "Fumigation is dangerous: only trained, authorised people should do it.",
            "For seed: use certified seed where possible, keep each lot labelled, do not use damp or insect-bitten seed, and do a simple germination test (count 100 seeds on damp cloth and see how many sprout in about a week) before sowing.",
            "Ask the KVK about seed treatment for your crop; use only the product and amount they advise, with gloves.",
        ],
        "source": TNAU, "videos": _videos("grain storage methods farmers weevil control tamil", "seed germination test farmers"),
    },
    "livestock": {
        "title": "Livestock basics: cattle, goats and poultry", "kind": "knowledge", "photos": ["cattle_cbe", "k_goat2"],
        "steps": [
            "Give a dry, clean, shaded shelter with a drained floor, and clean drinking water at all times.",
            "Feed green and dry fodder plus a mineral mixture; change feed slowly.",
            "Vaccinate on the Animal Husbandry Department schedule (foot-and-mouth disease, haemorrhagic septicaemia and black quarter are the common ones). The department runs vaccination camps, often free.",
            "Deworm on schedule and keep the animal's body and the shed free of ticks and flies.",
            "Separate any sick animal at once and call the nearest government veterinary dispensary or mobile veterinary unit; do not wait for it to get worse.",
            "Keep cattle and goats out of fields that were just sprayed, and do not feed fodder wet with pesticide.",
            "Keep animals off crops with a fence, bund or tethering (see the land-protection card), and note milk or weight records to spot illness early.",
        ],
        "notes": ["Do not give human or leftover medicines. Treatment and doses are for the veterinarian to decide."],
        "source": {"title": "Department of Animal Husbandry and Dairying (Government of India)", "url": "https://dahd.nic.in/"},
        "videos": _videos("cattle vaccination schedule FMD tamil", "goat rearing shed management farmers tamil"),
    },
    "marketing": {
        "title": "Selling your produce: prices, markets and farmer groups", "kind": "knowledge", "photos": ["k_market1", "k_market2"],
        "steps": [
            "Know the minimum support price (MSP) for your crop before you sell: ask Cropsy 'MSP of <crop>'.",
            "Check today's price on e-NAM, Agmarknet or the Uzhavan app, and in two nearby markets, before you agree a rate.",
            "In Tamil Nadu, Uzhavar Sandhai (farmers' markets) let you sell vegetables and fruit straight to buyers without a middleman.",
            "Clean, dry and grade the produce; better grading gets a better price. Keep weight slips and bills.",
            "Sell together: a Farmer Producer Organisation (FPO) or group cuts transport and gets a better rate for bigger lots. Ask the block agriculture office about one near you.",
            "If prices are low at harvest and you can store safely, a warehouse receipt loan lets you wait without a distress sale.",
        ],
        "notes": ["Prices change daily; this card gives no price. Ask Cropsy for MSP, and use the market sources above for today's rate."],
        "source": ENAM, "extra_sources": [TNAU],
        "videos": _videos("e-NAM how farmers sell online tamil", "Uzhavar Sandhai farmers market tamil nadu", "FPO farmer producer organisation how to form"),
    },
}

CAPTIONS = {
    "k_csc": "A Common Service Centre in Tirunelveli: where farmers register for schemes",
    "k_soil1": "Taking a soil sample from a small pit", "k_soil2": "Sampling at several spots across a field", "k_soillab": "A soil testing laboratory",
    "k_drip1": "Drip lines at the foot of banana plants", "k_drip2": "Drip tubing: flush and check it regularly",
    "k_paddy1": "Transplanting rice in Tamil Nadu", "k_paddy2": "A paddy field in Tamil Nadu",
    "k_spray": "A large tractor sprayer (on small plots you use a knapsack sprayer: same gear and wind rules)",
    "k_bin": "A traditional woven grain store: raised, covered and dry",
    "cattle_cbe": "Cattle grazing in an open field near Coimbatore", "k_goat2": "Goats grazing",
    "k_market1": "Uzhavar Sandhai (farmers' market) entrance", "k_market2": "Another Uzhavar Sandhai in Tamil Nadu",
}

# word patterns that open each card
TRIGGERS = [
    ("schemes", r"pm[\s-]?kisan|kisan\s+credit|\bkcc\b|crop\s+loan|farm\s+loan|subsid(y|ies)|government\s+schemes?|schemes?\s+for\s+farmers|\bpmfby\b|crop\s+insurance|insurance\s+claim|\bpmksy\b|\bkusum\b|solar\s+pump|\buzhavan\b|myscheme|மானியம்|காப்பீடு"),
    ("soil_sampling", r"soil\s+(sample|sampling|test|testing)|soil\s+health\s+card|test\s+(my\s+)?soil|மண்\s*(மாதிரி|பரிசோதனை)"),
    ("water_saving", r"\bdrip\b|sprinkler|mulch|water[\s-]?saving|save\s+water|alternate\s+wetting|\bawd\b|micro[\s-]?irrigation|சொட்டு\s*நீர்"),
    ("season", r"kuruvai|\bsamba\b|thaladi|navarai|crop\s+calendar|sowing\s+(season|time)|which\s+season|பட்டம்"),
    ("pesticide_safety", r"pesticide\s+(safety|handling|storage|disposal|gear|precaution)|safe(ly)?\s+(spray|use|handle)|re[\s-]?entry|spray(ing)?\s+(safety|precaution)|protective\s+(gear|clothing|equipment)|\bppe\b|bee\s+safe"),
    ("storage", r"(seed|grain|paddy|maize|groundnut|pulses?)\s+(storage|store|drying)|store\s+(my\s+)?(grain|paddy|seed|maize|groundnut|pulses)|post[\s-]?harvest|safe\s+moisture|(grain|seed|stored)\s+(weevil|insect|pest)s?|germination\s+test"),
    ("livestock", r"(cow|cattle|goat|sheep|buffalo|poultry|hen|livestock|dairy)s?\b.{0,40}(care|health|shed|vaccin\w*|feed|fodder|disease|manage\w*|sick)|vaccinat\w*.{0,15}(cow|cattle|goat|sheep|buffalo)|(cow|cattle|goat|sheep|buffalo)\w*.{0,15}vaccinat|animal\s+husbandry|கால்நடை"),
    ("marketing", r"\bmandi\b|\be-?nam\b|\bfpo\b|farmer\s+producer|uzhavar\s+(sandhai|santhai)|direct\s+selling|where\s+to\s+sell|how\s+to\s+sell|sell\s+(my|the)\s|selling\s+(my|the)\s|marketing\s+(my|of)|சந்தை"),
]
# these answer a question completely; "season" only adds a card under the normal TNAU answer
CARD_ONLY = {"season"}
