"""Build the 25-query evaluation set -> backend/data/queries.json.

Each query carries the route the pipeline should take, the facts the answer must contain (computed from
the dataset, never typed by hand) and, where relevant, an injected failure to demonstrate fallback.
Photo queries use HOLDOUT images only. Queries with split="unseen" must not be used for tuning/prompts.
Run after build_dataset.py and build_photo_index.py.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend" / "data"
parcels = {p["parcel_id"]: p for p in json.loads((DATA / "parcels.json").read_text(encoding="utf-8"))}
manifest = json.loads((DATA / "images" / "manifest.json").read_text(encoding="utf-8"))
holdout = {}
for it in manifest["items"]:
    if it["split"] == "holdout":
        holdout.setdefault((it["crop"], it["condition_code"]), []).append(it["file"])


CROP_OF = {"rice": "Rice", "cane": "Sugarcane", "maize": "Maize", "banana": "Banana", "coconut": "Coconut"}


def img(code, crop=None):
    crop = crop or CROP_OF[code.split("_")[0]]
    files = holdout.get((crop, code))
    return f"images/{files[0]}" if files else None


def facts(pid):
    p = parcels[pid]
    return {"parcel_id": pid, "crop": p["crop"]["name"], "variety": p["crop"]["variety"], "stage": p["crop"]["stage"],
            "days_after_planting": p["crop"]["days_after_planting"], "area_ha": p["area_ha"],
            "issue_code": p["observed_issue"]["code"], "issue": p["observed_issue"]["label"],
            "days_since_irrigation": p["management"]["days_since_last_irrigation"],
            "days_since_fertilizer": p["management"]["days_since_last_fertilizer"], "zone": p["zone"]}


# route values: ROUTINE (structured/calculator), ADVISORY (text RAG), VISUAL (image + retrieval),
# COMPLEX (multi-factor, Ministral 8B), INSUFFICIENT (must ask / refer to expert), OUT_OF_SCOPE
Q = [
    # ---- routine / calculation -------------------------------------------------------------
    dict(lang="en", q="Which growth stage is the crop in survey TM-03 and how many days after planting is it?",
         parcel="TM-03", route="ROUTINE", tools=["parcel_lookup", "stage_calendar"], must=["stage", "days_after_planting"]),
    dict(lang="tanglish", q="TM-11 maize ku ippo enna stage? Next enna pannanum?",
         parcel="TM-11", route="ADVISORY", tools=["parcel_lookup", "stage_calendar", "tnau_rag"], must=["stage"]),
    dict(lang="ta", q="TM-14 வாழை நட்டு எத்தனை நாள் ஆகிறது? அடுத்த உரம் எப்போது இட வேண்டும்?",
         parcel="TM-14", route="ADVISORY", tools=["parcel_lookup", "stage_calendar", "tnau_rag"], must=["stage", "days_after_planting"]),
    dict(lang="en", q="Calculate the urea, DAP and MOP quantity for the whole of TM-03 using the TNAU recommendation.",
         parcel="TM-03", route="ROUTINE", tools=["parcel_lookup", "fertilizer_calculator", "tnau_rag"], must=["area_ha"],
         inject="unit_error_in_first_answer", tests="verifier catches a wrong unit/number, retries once on Ministral 8B"),
    dict(lang="en", q="When was TM-02 last irrigated and is it due again?",
         parcel="TM-02", route="ROUTINE", tools=["parcel_lookup", "weather"], must=["days_since_irrigation"]),
    # ---- weather dependent -----------------------------------------------------------------
    dict(lang="en", q="Will it rain at TM-09 this week? Should I spray fungicide now?",
         parcel="TM-09", route="COMPLEX", tools=["parcel_lookup", "weather", "tnau_rag"], must=["issue", "forecast_rain"]),
    dict(lang="tanglish", q="Naalaiku mazhai varuma? TM-13 la fertilizer podalama?",
         parcel="TM-13", route="COMPLEX", tools=["parcel_lookup", "weather", "tnau_rag"], must=["days_since_fertilizer", "forecast_rain"]),
    dict(lang="en", q="Is TM-15 at risk from the coming rain?",
         parcel="TM-15", route="COMPLEX", tools=["parcel_lookup", "weather", "tnau_rag"], must=["zone", "issue", "forecast_rain"]),
    # ---- advisory / knowledge --------------------------------------------------------------
    dict(lang="en", q="How do I manage sheath blight in rice?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Rice"),
    dict(lang="ta", q="நெல்லில் குலை நோயை (blast) எப்படி கட்டுப்படுத்துவது?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Rice"),
    dict(lang="en", q="What spacing and seed rate should I use for Co 86032 sugarcane?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Sugarcane"),
    dict(lang="tanglish", q="Coconut ku potash eppo, evlo podanum?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Coconut"),
    # ---- photo (holdout images only) -------------------------------------------------------
    dict(lang="en", q="What is wrong with my paddy leaf?", parcel="TM-09", image=img("rice_blast"), route="VISUAL",
         tools=["vision_symptoms", "image_retrieval", "parcel_lookup", "tnau_rag"], must=["issue", "stage"], split="unseen",
         expect_condition="rice_blast"),
    dict(lang="tanglish", q="Intha karumbu ilai la red color irukku, enna problem?", parcel="TM-04", image=img("cane_red_rot"),
         route="VISUAL", tools=["vision_symptoms", "image_retrieval", "parcel_lookup", "tnau_rag"], must=["issue", "stage"],
         split="unseen", expect_condition="cane_red_rot"),
    # photo + "what should I spray" = diagnose AND recommend, so it is COMPLEX (still Ministral 8B)
    dict(lang="en", q="Is this serious? What should I spray?", parcel="TM-05", image=img("maize_fall_armyworm"), route="COMPLEX",
         tools=["vision_symptoms", "image_retrieval", "parcel_lookup", "tnau_rag"], must=["issue", "stage"], split="unseen",
         expect_condition="maize_fall_armyworm"),
    dict(lang="en", q="Check this banana leaf and tell me the treatment.", parcel="TM-06", image=img("banana_sigatoka"),
         route="VISUAL", tools=["vision_symptoms", "image_retrieval", "parcel_lookup", "tnau_rag"], must=["issue", "stage"],
         split="unseen", expect_condition="banana_sigatoka"),
    dict(lang="en", q="Is my sugarcane healthy? Do I need to spray anything?", parcel="TM-10", image=img("healthy", "Sugarcane"),
         route="VISUAL", tools=["vision_symptoms", "image_retrieval", "parcel_lookup"], must=["stage"], split="unseen",
         expect_condition="healthy", tests="must NOT recommend an unnecessary spray on a healthy crop"),
    # ---- complex multi-factor (Ministral 8B) -----------------------------------------------
    dict(lang="en", q="TM-09 has blast lesions and rain is forecast. What should I do over the next 7 days?",
         parcel="TM-09", route="COMPLEX", tools=["parcel_lookup", "weather", "tnau_rag"], must=["issue", "stage", "forecast_rain"],
         split="unseen"),
    dict(lang="en", q="TM-13 is at flowering with sheath blight, heavy rain is coming and fertilizer was applied 10 days ago. Plan the next week.",
         parcel="TM-13", route="COMPLEX", tools=["parcel_lookup", "weather", "tnau_rag"], must=["issue", "stage", "forecast_rain"],
         split="unseen"),
    dict(lang="ta", q="TM-15 கரும்பு வயலில் இலை மஞ்சளாக உள்ளது, மழை வரப்போகிறது. என்ன செய்யலாம்?",
         parcel="TM-15", route="COMPLEX", tools=["parcel_lookup", "weather", "tnau_rag"], must=["zone", "issue", "forecast_rain"],
         split="unseen"),
    dict(lang="en", q="Compare the yield history and current problems of TM-04 and TM-10 and suggest what to change this season.",
         parcel="TM-04", also=["TM-10"], route="COMPLEX", tools=["parcel_lookup", "history", "tnau_rag"], must=["issue"],
         split="unseen"),
    # ---- insufficient evidence / out of scope / failure injection --------------------------
    dict(lang="en", q="My banana leaves have big brown spots with a yellow halo. What is the treatment?", parcel="TM-02",
         image=img("banana_cordana"), route="INSUFFICIENT", tools=["vision_symptoms", "image_retrieval", "tnau_rag"],
         must=["says_evidence_insufficient", "refers_to_expert"], expect_condition="banana_cordana", split="unseen",
         tests="corpus has no TNAU advice for Cordana -> must NOT invent a dose"),
    dict(lang="en", q="What pesticide dose should I use for pink bollworm in cotton at TM-05?", parcel="TM-05",
         route="OUT_OF_SCOPE", tools=["parcel_lookup"], must=["crop_mismatch_flagged"],
         tests="parcel grows maize; cotton is outside the corpus -> flag mismatch, do not answer from memory"),
    dict(lang="en", q="How many parcels in Then Malai are growing rice, and what is their total area?", parcel=None,
         route="ROUTINE", tools=["village_query"], must=["count", "total_area_ha"]),
    dict(lang="en", q="This is a photo of my paddy field. Which stage is it in and does it look healthy?", parcel="TM-03",
         image="images/rice/field_scene/rice_tm-03_wide_field.jpg", route="VISUAL",
         tools=["vision_symptoms", "image_retrieval", "parcel_lookup", "stage_calendar"], must=["crop", "stage"],
         split="unseen", expect_condition="field_scene",
         tests="wide field photo: crop from photo, stage from planting date, must NOT claim a confident disease diagnosis"),
    dict(lang="en", q="What is the weather at TM-05 for the next 3 days?", parcel="TM-05", route="ROUTINE",
         tools=["weather"], must=["forecast_rain", "marks_cached_data"], inject="open_meteo_timeout",
         tests="live weather fails -> falls back to cached forecast and says so"),
    # ---- added crops (general advisory, no parcel) -----------------------------------------
    dict(lang="en", q="How do I control rust and leaf spot in groundnut?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Groundnut"),
    dict(lang="en", q="Which pre-emergence herbicide is recommended for cotton?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Cotton"),
    dict(lang="tanglish", q="Ulundu la yellow mosaic varama irukku, enna pannanum?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Blackgram"),
    dict(lang="en", q="What is the spacing for chilli and which fungicide for leaf spot?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Chilli"),
    dict(lang="en", q="How do I prevent rhizome rot in turmeric?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Turmeric"),
    dict(lang="en", q="Which cotton variety should I plant for long staple?", parcel=None, route="ADVISORY",
         tools=["tnau_rag"], must=["cited_source"], crop="Cotton"),
]

rice = [p for p in parcels.values() if p["crop"]["name"] == "Rice"]
out = []
for i, q in enumerate(Q, 1):
    rec = {"id": f"Q{i:02d}", "language": q["lang"], "query": q["q"], "parcel_id": q["parcel"],
           "image": q.get("image"), "expected_route": q["route"], "expected_tools": q["tools"],
           "answer_must_contain": q["must"], "split": q.get("split", "dev"), "inject_failure": q.get("inject"),
           "tests": q.get("tests"), "expect_condition": q.get("expect_condition"), "crop": q.get("crop")}
    pids = ([q["parcel"]] if q["parcel"] else []) + q.get("also", [])
    rec["facts"] = {pid: facts(pid) for pid in pids}
    if q["tools"] == ["village_query"]:
        rec["facts"] = {"rice_parcel_count": len(rice), "rice_total_area_ha": round(sum(p["area_ha"] for p in rice), 2)}
    if q.get("image") is None and q["route"] == "VISUAL":
        rec["warning"] = "no holdout image available for this class yet"
    out.append(rec)

(DATA / "queries.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(len(out), "queries |", dict(Counter(r["expected_route"] for r in out)), "|", dict(Counter(r["language"] for r in out)))
print("unseen:", sum(r["split"] == "unseen" for r in out), "| with image:", sum(bool(r["image"]) for r in out),
      "| failure injections:", sum(bool(r["inject_failure"]) for r in out))
print("warnings:", [r["id"] for r in out if r.get("warning")])
