"""Build the Then Malai dataset for Cropsy (all 120 parcels).

Order:  python backend/scripts/build_village.py   (geometry + zones)
        python backend/scripts/build_dataset.py   (this file: profiles, issues, history, weather)
Real:  coordinates, elevation, soil, terrain shadow of the 16 anchor parcels (Copernicus DEM / NOAA).
Dummy: owners, crops, stages, issues, management, history, weather.  Deterministic (SEED).
"""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "dataset" / "then_malai" / "then_malai_parcels.csv"
OUT = ROOT / "backend" / "data"
AS_OF = date(2026, 10, 3)
SEED = 36
DUMMY = "dummy"

STAGES = {
    "Rice": [(0, 15, "Establishment"), (16, 40, "Tillering"), (41, 60, "Panicle Initiation"),
             (61, 80, "Flowering"), (81, 100, "Milk / Dough"), (101, 130, "Maturity")],
    "Banana": [(0, 60, "Establishment"), (61, 150, "Vegetative"), (151, 210, "Flower Initiation"),
               (211, 270, "Shooting"), (271, 330, "Bunch Development"), (331, 420, "Harvest")],
    "Sugarcane": [(0, 35, "Germination"), (36, 120, "Tillering"), (121, 270, "Grand Growth"),
                  (271, 400, "Maturity")],
    "Maize": [(0, 10, "Emergence"), (11, 35, "Vegetative"), (36, 55, "Tasseling"),
              (56, 70, "Silking"), (71, 95, "Grain Filling"), (96, 120, "Maturity")],
    # added crops: stage day-bands are approximate durations (TNAU crop duration), not exact TNAU stage tables
    "Groundnut": [(0, 10, "Emergence"), (11, 30, "Vegetative"), (31, 45, "Flowering"), (46, 75, "Pegging & Pod Formation"),
                  (76, 100, "Pod Development"), (101, 125, "Maturity")],
    "Cotton": [(0, 20, "Emergence"), (21, 60, "Vegetative"), (61, 90, "Squaring"), (91, 120, "Flowering & Boll Formation"),
               (121, 150, "Boll Development"), (151, 200, "Boll Opening & Picking")],
    "Blackgram": [(0, 10, "Emergence"), (11, 30, "Vegetative"), (31, 45, "Flowering"), (46, 60, "Pod Formation"),
                  (61, 85, "Maturity")],
    "Chilli": [(0, 20, "Establishment"), (21, 60, "Vegetative"), (61, 90, "Flowering"), (91, 150, "Fruiting & Picking"),
               (151, 220, "Late Picking")],
    "Turmeric": [(0, 45, "Establishment"), (46, 120, "Vegetative"), (121, 210, "Rhizome Bulking"), (211, 270, "Maturity"),
                 (271, 320, "Harvest")],
}

# Parcels re-assigned to the added crops (the satellite/geometry side of every parcel is unchanged).
# parcel -> (crop, variety, planting_date); chosen by build_new_crop_assignment() below, stored here once decided.
NEW_CROPS = {
    "Groundnut": ["VRI 8", "TMV 14", "CO 7"], "Cotton": ["MCU 5", "SVPR 2", "KC 3"], "Blackgram": ["VBN 6"],
    "Chilli": ["K 2", "CO 1"], "Turmeric": ["CO 1", "BSR 2"],
}
NEW_PLANT = {"Groundnut": ("2026-08-15", 25), "Cotton": ("2026-08-30", 20), "Blackgram": ("2026-09-05", 15),
             "Chilli": ("2026-08-10", 20), "Turmeric": ("2026-06-10", 20)}
NEW_FROM = {"Groundnut": "Maize", "Cotton": "Maize", "Blackgram": "Maize", "Chilli": "Maize", "Turmeric": "Sugarcane"}
NEW_PER_CROP = 5
# issue pools for the added crops: every issue here has real reference photos AND a verified TNAU control
NEW_POOL = {
    "Groundnut": [("healthy", .4), ("groundnut_rust", .3), ("groundnut_leaf_spot", .3)],
    "Cotton": [("healthy", .4), ("cotton_bacterial_blight", .25), ("cotton_alternaria_leaf_spot", .2), ("cotton_wilt", .15)],
    "Blackgram": [("healthy", .35), ("blackgram_yellow_mosaic", .35), ("blackgram_powdery_mildew", .3)],
    "Chilli": [("healthy", .4), ("chilli_leaf_spot", .3), ("chilli_powdery_mildew", .3)],
    "Turmeric": [("healthy", .5), ("turmeric_leaf_spot", .5)],
}


def _i(label, crop, kind, sev, symptoms, photo_class=None):
    """photo_class: folder name in the real photo set, or None when there is no photo class (nutrient/abiotic)."""
    return dict(label=label, crop=crop, kind=kind, severity=sev, symptoms=symptoms, photo_class=photo_class,
                symptoms_source="general agronomy description - verify against TNAU before citing")


ISSUES = {
    "healthy": _i("Healthy crop", "any", "none", "none", ["uniform green canopy", "no visible lesions or pests"], "healthy"),
    # rice (RiceLeafBD)
    "rice_blast": _i("Rice blast", "Rice", "disease", "moderate",
                     ["spindle-shaped spots with grey centres", "brown margins on leaves"], "Blast"),
    "rice_sheath_blight": _i("Sheath blight", "Rice", "disease", "moderate",
                             ["oval greenish-grey lesions on sheath near water line", "lesions spreading upward"], "Sheath_Blight"),
    "rice_narrow_brown_spot": _i("Narrow brown leaf spot", "Rice", "disease", "mild",
                                 ["short narrow brown linear lesions on leaves", "lesions parallel to veins"], "Narrow_Brown_Spot"),
    "rice_tungro": _i("Rice tungro", "Rice", "disease", "severe",
                      ["orange-yellow discolouration of leaves", "stunted plants", "reduced tillering"], "Tungro"),
    # banana (BananaLSD)
    "banana_sigatoka": _i("Sigatoka leaf spot", "Banana", "disease", "moderate",
                          ["yellow streaks turning brown", "grey-centred spots on older leaves"], "sigatoka"),
    "banana_cordana": _i("Cordana leaf spot", "Banana", "disease", "mild",
                         ["large oval brown lesions with yellow halo", "lesions drying from the centre"], "cordana"),
    "banana_pestalotiopsis": _i("Pestalotiopsis leaf spot", "Banana", "disease", "mild",
                                ["dark brown irregular spots with grey centres", "spots often on leaf margins"], "pestalotiopsis"),
    "banana_k_deficiency": _i("Potassium deficiency", "Banana", "nutrient", "mild",
                              ["scorched yellow leaf margins on older leaves", "premature leaf drying"]),
    # added crops: kept in the catalog so the field report can list their watch-list with TNAU controls. They are not in the
    # generated-parcel POOL (no photo class), so no parcel is assigned these issues.
    "groundnut_rust": _i("Groundnut rust", "Groundnut", "disease", "moderate", ["orange-brown pustules on the underside of leaves", "leaves drying early"]),
    "groundnut_leaf_spot": _i("Early / late leaf spot", "Groundnut", "disease", "moderate", ["dark brown to black circular spots on leaves", "yellow halo, premature leaf fall"]),
    "groundnut_root_rot": _i("Root rot", "Groundnut", "disease", "severe", ["sudden wilting of plants", "rotted dark roots and collar"]),
    "cotton_bacterial_blight": _i("Bacterial blight", "Cotton", "disease", "moderate", ["angular water-soaked leaf spots", "black arm on stems in severe cases"]),
    "cotton_alternaria_leaf_spot": _i("Alternaria leaf spot", "Cotton", "disease", "mild", ["brown circular spots with concentric rings", "premature leaf drop"]),
    "cotton_wilt": _i("Fusarium wilt / damping off", "Cotton", "disease", "severe", ["yellowing and wilting of plants", "brown discolouration of stem vessels"]),
    "blackgram_yellow_mosaic": _i("Yellow mosaic", "Blackgram", "disease", "severe", ["bright yellow patches on leaves", "stunting, few pods"]),
    "blackgram_powdery_mildew": _i("Powdery mildew", "Blackgram", "disease", "moderate", ["white powdery growth on leaves", "leaves drying"]),
    "blackgram_rust": _i("Rust", "Blackgram", "disease", "moderate", ["reddish-brown pustules on leaves"]),
    "blackgram_leaf_spot": _i("Cercospora leaf spot", "Blackgram", "disease", "mild", ["small brown spots with grey centres on leaves"]),
    "chilli_leaf_spot": _i("Leaf spot", "Chilli", "disease", "mild", ["brown spots on leaves", "leaf drop"]),
    "chilli_powdery_mildew": _i("Powdery mildew", "Chilli", "disease", "moderate", ["white powdery patches on the underside of leaves", "yellowing and leaf drop"]),
    "chilli_anthracnose": _i("Anthracnose", "Chilli", "disease", "moderate", ["sunken dark spots on ripe fruits"]),
    "chilli_die_back_fruit_rot": _i("Die-back and fruit rot", "Chilli", "disease", "severe", ["drying of twigs from the tip", "rotting fruits"]),
    "turmeric_rhizome_rot": _i("Rhizome rot", "Turmeric", "disease", "severe", ["yellowing of lower leaves", "soft rotting rhizomes"]),
    "turmeric_leaf_spot": _i("Leaf blotch and leaf spot", "Turmeric", "disease", "moderate", ["brown spots on leaves merging into blotches"]),
    # sugarcane
    "cane_red_rot": _i("Red rot", "Sugarcane", "disease", "severe",
                       ["reddening of leaf midrib", "drying of top leaves", "red internal stalk tissue with white patches"], "RedRot"),
    "cane_rust": _i("Sugarcane rust", "Sugarcane", "disease", "moderate",
                    ["small elongated reddish-brown pustules on both leaf surfaces", "leaf yellowing and drying"], "Rust"),
    "cane_mosaic": _i("Sugarcane mosaic", "Sugarcane", "disease", "moderate",
                      ["light and dark green mosaic pattern on leaves", "stunting"], "Mosaic"),
    "cane_yellow_leaf": _i("Yellow leaf disease", "Sugarcane", "disease", "moderate",
                           ["yellowing of leaf midrib from the underside", "leaf yellowing from the tip"], "Yellow"),
    "cane_waterlogging_chlorosis": _i("Waterlogging / iron chlorosis", "Sugarcane", "abiotic", "moderate",
                                      ["yellow young leaves with green veins", "standing water in furrows"]),
    # maize (MLD)
    "maize_fall_armyworm": _i("Fall armyworm", "Maize", "pest", "moderate",
                              ["ragged holes in leaves", "sawdust-like frass in whorl"], "Fall_Armyworm"),
    "maize_gray_leaf_spot": _i("Gray leaf spot", "Maize", "disease", "moderate",
                               ["rectangular grey-tan lesions between veins", "lesions merge on lower leaves"], "Gray_Spot"),
    "maize_leaf_blight": _i("Leaf blight", "Maize", "disease", "moderate",
                            ["long elliptical grey-green to tan lesions", "lesions spreading across leaf"], "Leaf_Blight"),
    "maize_n_deficiency": _i("Nitrogen deficiency", "Maize", "nutrient", "mild",
                             ["V-shaped yellowing from leaf tip", "pale lower leaves"]),
    # coconut (Coconut Tree Disease dataset - class folders confirmed once the download completes)
    "coconut_gray_leaf_spot": _i("Gray leaf spot", "Coconut", "disease", "mild",
                                 ["small brown spots with grey centres and yellow halo on leaflets"], "gray_leaf_spot"),
    "coconut_bud_rot": _i("Bud rot", "Coconut", "disease", "severe",
                          ["spindle leaf yellowing and drooping", "rotting of the central bud"], "bud_rot"),
    "coconut_leaf_rot": _i("Leaf rot", "Coconut", "disease", "moderate",
                           ["rotting and browning of leaflet tips and fronds"], "leaf_rot"),
    "coconut_k_deficiency": _i("Potassium deficiency", "Coconut", "nutrient", "mild",
                               ["orange-yellow mottling on lower fronds", "necrosis on leaflet tips"]),
}

# anchor parcels: survey_no -> (crop, variety, planting_date, issue_code, issue_since_days)
STORY = {
    "TM-01": ("Coconut", "West Coast Tall", "2019-06-15", "coconut_k_deficiency", 40),
    "TM-02": ("Banana", "Grand Naine", "2026-01-05", "banana_cordana", 12),
    "TM-03": ("Rice", "ADT 45", "2026-08-25", "rice_narrow_brown_spot", 6),
    "TM-04": ("Sugarcane", "Co 86032", "2026-04-15", "cane_red_rot", 15),
    "TM-05": ("Maize", "Hybrid CO 6", "2026-08-10", "maize_fall_armyworm", 8),
    "TM-06": ("Banana", "Nendran", "2026-05-20", "banana_sigatoka", 21),
    "TM-07": ("Coconut", "West Coast Tall", "2018-09-10", "healthy", 0),
    "TM-08": ("Banana", "Grand Naine", "2026-03-10", "banana_k_deficiency", 18),
    "TM-09": ("Rice", "ADT 45", "2026-08-10", "rice_blast", 7),
    "TM-10": ("Sugarcane", "Co 86032", "2026-03-01", "healthy", 0),
    "TM-11": ("Maize", "Hybrid CO 6", "2026-07-25", "healthy", 0),
    "TM-12": ("Coconut", "Chowghat Orange Dwarf x WCT", "2017-10-15", "coconut_gray_leaf_spot", 30),
    "TM-13": ("Rice", "ADT 45", "2026-07-25", "rice_sheath_blight", 10),
    "TM-14": ("Banana", "Nendran", "2026-07-25", "healthy", 0),
    "TM-15": ("Sugarcane", "Co 86032", "2026-06-20", "cane_waterlogging_chlorosis", 5),
    "TM-16": ("Maize", "Hybrid CO 6", "2026-08-20", "maize_n_deficiency", 9),
}

# issue pool for the generated parcels: crop -> [(issue_code, weight)]
POOL = {
    "Rice": [("healthy", .30), ("rice_blast", .20), ("rice_sheath_blight", .20), ("rice_narrow_brown_spot", .15), ("rice_tungro", .15)],
    "Banana": [("healthy", .30), ("banana_sigatoka", .30), ("banana_cordana", .15), ("banana_pestalotiopsis", .10), ("banana_k_deficiency", .15)],
    "Sugarcane": [("healthy", .28), ("cane_red_rot", .14), ("cane_rust", .20), ("cane_mosaic", .10), ("cane_yellow_leaf", .10), ("cane_waterlogging_chlorosis", .18)],
    "Maize": [("healthy", .30), ("maize_fall_armyworm", .25), ("maize_gray_leaf_spot", .15), ("maize_leaf_blight", .15), ("maize_n_deficiency", .15)],
    "Groundnut": [("healthy", 1.0)], "Cotton": [("healthy", 1.0)], "Blackgram": [("healthy", 1.0)],
    "Chilli": [("healthy", 1.0)], "Turmeric": [("healthy", 1.0)],
    "Coconut": [("healthy", .35), ("coconut_gray_leaf_spot", .20), ("coconut_bud_rot", .08), ("coconut_leaf_rot", .15), ("coconut_k_deficiency", .22)],
}

YIELD = {"Rice": (4.8, 6.4, "t/ha"), "Banana": (36, 54, "t/ha"), "Sugarcane": (95, 120, "t/ha"),
         "Maize": (5.5, 8.0, "t/ha"), "Coconut": (85, 135, "nuts/palm/year"),
         "Groundnut": (1.8, 2.6, "t/ha pods"), "Cotton": (1.6, 2.4, "t/ha seed cotton"), "Blackgram": (0.6, 0.9, "t/ha"),
         "Chilli": (1.2, 2.0, "t/ha dry chilli"), "Turmeric": (20, 28, "t/ha fresh rhizome")}
FERT = {"Rice": "Urea + DAP + MOP (TNAU basal/top-dress split)", "Banana": "Urea + MOP in 5 splits",
        "Sugarcane": "Urea + SSP + MOP with trash mulch", "Maize": "NPK basal + urea top-dress",
        "Coconut": "NPK 500:320:1200 g/palm + FYM",
        "Groundnut": "Basal NPK + gypsum at flowering", "Cotton": "NPK in splits with top-dress",
        "Blackgram": "Basal DAP + Rhizobium seed treatment", "Chilli": "FYM + NPK in splits",
        "Turmeric": "FYM + NPK in splits"}
IRRIG = {"Rice": "flood / alternate wetting-drying", "Banana": "drip", "Sugarcane": "drip",
         "Maize": "furrow", "Coconut": "basin flood",
         "Groundnut": "furrow / sprinkler", "Cotton": "drip", "Blackgram": "rainfed with life irrigation",
         "Chilli": "drip", "Turmeric": "drip"}
WILDLIFE = {"foothill": ("Wild boar / bonnet macaque", "Frequent (weekly)", "high_foothill_boundary"),
            "terrace": ("Wild boar (occasional)", "Occasional (fortnightly)", "moderate"),
            "valley": ("Stray cattle", "Rare", "low_valley_basin")}


def stage_for(crop, planting, as_of):
    dap = (as_of - planting).days
    if crop == "Coconut":
        return dap, "Mature bearing palm - nut development phase"
    for lo, hi, name in STAGES[crop]:
        if lo <= dap <= hi:
            return dap, name
    return dap, STAGES[crop][-1][2]


def weighted(rnd, opts):
    r, acc = rnd.random(), 0.0
    for name, w in opts:
        acc += w
        if r <= acc:
            return name
    return opts[-1][0]


def num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def main():
    rnd = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "weather").mkdir(exist_ok=True)

    geom = {f["id"]: f for f in json.loads((OUT / "village_geometry.geojson").read_text(encoding="utf-8"))["features"]}
    csv_rows = {r["survey_no"]: r for r in csv.DictReader(open(SRC, encoding="utf-8"))}

    # re-assign some generated parcels to the added crops. The original crop is kept as `old_crop` so the random
    # stream (issues, management, history) of every other parcel is exactly what it was before.
    pick = random.Random(f"{SEED}-new-crops")
    for crop, old in NEW_FROM.items():
        pool = sorted(pid for pid, f in geom.items() if pid not in csv_rows and f["properties"]["crop"] == old
                      and "old_crop" not in f["properties"])
        for pid in pick.sample(pool, NEW_PER_CROP):
            g = geom[pid]["properties"]
            base, jitter = NEW_PLANT[crop]
            g["old_crop"] = old
            g["crop"] = crop
            g["variety"] = pick.choice(NEW_CROPS[crop])
            g["planting_date"] = (date.fromisoformat(base) + timedelta(days=pick.randint(-jitter, jitter))).isoformat()

    parcels, features = [], []
    for pid, feat in geom.items():
        g = feat["properties"]
        zone = g["zone"]
        if pid in csv_rows:  # anchor: real geo/soil/terrain from the source CSV
            r = csv_rows[pid]
            crop, variety, plant, issue_code, since = STORY[pid]
            planting = date.fromisoformat(plant)
            loc = dict(lat=num(r["lat"]), lon=num(r["lon"]), elevation_m=num(r["elevation_m"]))
            soil = dict(texture=r["soil_texture"], ph=num(r["soil_ph"]), sand_pct=num(r["sand_pct"]),
                        silt_pct=num(r["silt_pct"]), clay_pct=num(r["clay_pct"]))
            terrain = dict(slope=r["SAMPLE_land_shape_slope"], max_horizon_angle_deg=num(r["max_horizon_angle_deg"]),
                           direct_sun_hours=num(r["direct_sun_hours"]), drainage_risk=r["drainage_risk"],
                           waterlogging_susceptibility=r["waterlogging_susceptibility"])
            owner = dict(name=r["SAMPLE_owner_name"], patta_no=r["SAMPLE_patta_no"])
            field_name, area = r["SAMPLE_field_name"], num(r["SAMPLE_land_area_hectares"])
            irr_days = int(num(r["SAMPLE_days_since_last_irrigation"], 3))
            fert_days = int(num(r["SAMPLE_days_since_last_fertilizer"], 20))
            water_ph = num(r["SAMPLE_water_ph"])
            wild = dict(intrusion_type=r["SAMPLE_animal_intrusion_type"], frequency=r["SAMPLE_animal_intrusion_frequency"],
                        regional_risk=r["wildlife_regional_risk"])
            prov = "location/soil/terrain: real (Copernicus DEM 30m, NOAA solar geometry); owner/crop/management/issue: dummy"
        else:  # generated parcel
            crop, variety = g["crop"], g["variety"]
            planting = date.fromisoformat(g["planting_date"])
            issue_code = weighted(rnd, POOL[g.get("old_crop", crop)])
            if issue_code == "cane_waterlogging_chlorosis" and zone != "valley":
                issue_code = "healthy"
            since = 0 if issue_code == "healthy" else rnd.randint(3, 30)
            if crop in NEW_CROPS:       # added crops: own random stream, so the other parcels' draws are untouched
                nrnd = random.Random(f"{SEED}-{pid}-issue")
                issue_code = weighted(nrnd, NEW_POOL[crop])
                since = 0 if issue_code == "healthy" else nrnd.randint(3, 30)
            loc = dict(lat=g["lat"], lon=g["lon"], elevation_m=float(g["elevation_m"]))
            soil = dict(texture=g["soil_texture"], ph=g["soil_ph"], sand_pct=g.get("sand_pct"),
                        silt_pct=g.get("silt_pct"), clay_pct=g.get("clay_pct"))
            terrain = dict(slope={"valley": "Flat alluvial valley bottom", "terrace": "Gentle terraced slope",
                                  "foothill": "Foothill ridge slope"}[zone], max_horizon_angle_deg=None,
                           direct_sun_hours=None, drainage_risk=g["drainage_risk"],
                           waterlogging_susceptibility="high" if zone == "valley" else "low")
            owner = dict(name=g["owner"], patta_no=g["patta_no"])
            field_name, area = f"{crop} plot {pid}", g["area_ha"]
            irr_days, fert_days = rnd.randint(1, 10), rnd.randint(5, 60)
            water_ph = round(rnd.uniform(6.5, 7.4), 1)
            w = WILDLIFE[zone]
            wild = dict(intrusion_type=w[0], frequency=w[1], regional_risk=w[2])
            prov = "elevation: real (Copernicus DEM); everything else: dummy"

        dap, stage = stage_for(crop, planting, AS_OF)
        issue = ISSUES[issue_code]
        rec = {
            "parcel_id": pid, "survey_no": pid, "anchor": pid in csv_rows, "village": "Then Malai", "zone": zone,
            "location": loc, "soil": soil, "terrain": terrain, "owner": owner, "field_name": field_name,
            "area_ha": area,
            "crop": {"name": crop, "variety": variety, "planting_date": planting.isoformat(),
                     "days_after_planting": dap, "stage": stage},
            "management": {"days_since_last_irrigation": irr_days, "days_since_last_fertilizer": fert_days,
                           "irrigation_type": IRRIG[crop], "fertilizer_programme": FERT[crop], "water_ph": water_ph},
            "observed_issue": {"code": issue_code, "label": issue["label"], "kind": issue["kind"],
                               "severity": issue["severity"], "symptoms": issue["symptoms"],
                               "photo_class": issue["photo_class"], "since_days": since},
            "wildlife": wild,
            "provenance": {"note": prov, "as_of": AS_OF.isoformat()},
            "data_source": DUMMY,
        }
        parcels.append(rec)
        props = {"parcel_id": pid, "anchor": rec["anchor"], "zone": zone, "crop": crop, "variety": variety,
                 "stage": stage, "days_after_planting": dap, "planting_date": planting.isoformat(),
                 "area_ha": area, "owner": owner["name"], "patta_no": owner["patta_no"],
                 "issue_code": issue_code, "issue": issue["label"], "severity": issue["severity"],
                 "kind": issue["kind"], "elevation_m": loc["elevation_m"], "soil_texture": soil["texture"],
                 "soil_ph": soil["ph"], "drainage_risk": terrain["drainage_risk"], "lat": loc["lat"],
                 "lon": loc["lon"], "data_source": DUMMY}
        features.append({"type": "Feature", "id": pid, "properties": props, "geometry": feat["geometry"]})

    (OUT / "parcels.json").write_text(json.dumps(parcels, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "village_parcels.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "name": "then_malai_parcels", "features": features}, ensure_ascii=False), encoding="utf-8")
    cols = list(features[0]["properties"])
    with open(OUT / "village_parcels.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        wr.writerows(f["properties"] for f in features)

    (OUT / "village.json").write_text(json.dumps({
        "village": "Then Malai", "taluk": "Sengottai", "district": "Tenkasi", "state": "Tamil Nadu",
        "centre": {"lat": 8.91, "lon": 77.32}, "parcel_count": len(parcels), "as_of": AS_OF.isoformat(),
        "climate_note": "Western Ghats foothill; SW monsoon Jun-Sep, NE monsoon Oct-Dec",
        "note": "Demo village. Administrative hierarchy and all parcel/owner/crop records are dummy; only "
                "anchor-parcel coordinates, elevation, soil and terrain shadow are real.",
        "data_source": DUMMY}, indent=2), encoding="utf-8")
    (OUT / "issue_catalog.json").write_text(json.dumps(ISSUES, indent=2), encoding="utf-8")
    (OUT / "crop_stages.json").write_text(json.dumps(
        {c: [{"from_day": a, "to_day": b, "stage": s} for a, b, s in t] for c, t in STAGES.items()}, indent=2), encoding="utf-8")

    # history: 5 seasons per parcel
    with open(OUT / "history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["parcel_id", "year", "crop", "variety", "yield_value", "yield_unit", "fertilizer_used",
                    "irrigation_type", "major_issue", "data_source"])
        for p in parcels:
            crop = p["crop"]["name"]
            lo, hi, unit = YIELD[crop]
            base = rnd.uniform(lo, hi)
            for yr in range(2021, 2026):
                issue = rnd.choice(["none", "none", p["observed_issue"]["label"], "dry spell stress", "heavy rain lodging"])
                y = base * rnd.uniform(0.9, 1.08) * (0.88 if issue != "none" else 1.0)
                if crop == "Coconut" and yr < 2022 and p["crop"]["planting_date"] > "2018-12-31":
                    y *= 0.7
                w.writerow([p["parcel_id"], yr, crop, p["crop"]["variety"], round(y, 1), unit,
                            p["management"]["fertilizer_programme"], p["management"]["irrigation_type"], issue, DUMMY])

    # weather: 90 observed days + 7 forecast per parcel (elevation lapse, orographic rain factor)
    day0 = AS_OF - timedelta(days=89)
    storm = {AS_OF + timedelta(days=2): 38.0, AS_OF + timedelta(days=3): 22.0}
    with open(OUT / "weather" / "daily.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["parcel_id", "date", "kind", "tmax_c", "tmin_c", "rain_mm", "humidity_pct",
                    "wind_kmh", "et0_mm", "data_source"])
        for p in parcels:
            elev = p["location"]["elevation_m"]
            lapse = (elev - 165) * 0.0065
            rain_factor = 1.0 + max(0, elev - 165) / 600
            prng = random.Random(f"{SEED}-{p['parcel_id']}")
            for i in range(97):
                d = day0 + timedelta(days=i)
                kind = "observed" if d <= AS_OF else "forecast"
                monsoon = d.month in (10, 11) or (d.month in (6, 7, 8, 9) and prng.random() < 0.35)
                wet = prng.random() < (0.55 if d.month == 10 else 0.30 if monsoon else 0.12)
                rain = round(prng.expovariate(1 / 9) * rain_factor, 1) if wet else 0.0
                if kind == "forecast" and d in storm:
                    rain, wet = round(storm[d] * rain_factor, 1), True
                tmax = round(prng.gauss(33.0 if not wet else 29.5, 1.4) - lapse, 1)
                tmin = round(prng.gauss(24.0, 0.9) - lapse, 1)
                hum = int(min(98, max(45, prng.gauss(86 if wet else 72, 6))))
                w.writerow([p["parcel_id"], d.isoformat(), kind, tmax, tmin, rain, hum,
                            round(prng.uniform(4, 16), 1), round(prng.uniform(3.2, 5.4), 1), DUMMY])

    from collections import Counter
    print(f"parcels: {len(parcels)} (anchors {sum(p['anchor'] for p in parcels)})")
    print("issues:", dict(Counter(p['observed_issue']['code'] for p in parcels)))
    print("stages:", dict(Counter((p['crop']['name'], p['crop']['stage']) for p in parcels)))


if __name__ == "__main__":
    main()
