"""Build the Then Malai crop photo library from the real public datasets in dataset/raw_photos.

Selects N_TRAIN + N_HOLDOUT images per class, resizes them (max side 768), writes them to
backend/data/images/<crop>/<issue_code>/ and records provenance in backend/data/images/manifest.json.
Run again after new datasets are extracted:  python backend/scripts/build_photo_index.py
"""
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # copy without resizing
    Image = None

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "dataset" / "raw_photos"
OUT = ROOT / "backend" / "data" / "images"
ISSUES = json.loads((ROOT / "backend" / "data" / "issue_catalog.json").read_text(encoding="utf-8"))
N_TRAIN, N_HOLDOUT, SEED = 40, 8, 36

# dataset folder -> (crop, source name, source page, class-folder-name(lowercase) -> issue code)
SOURCES = {
    "rice_leafbd": ("Rice", "RiceLeafBD (Mendeley Data)", "https://data.mendeley.com/datasets/sjkptpgv79/1",
                    {"blast": "rice_blast", "sheath_blight": "rice_sheath_blight",
                     "narrow_brown_spot": "rice_narrow_brown_spot", "tungro": "rice_tungro", "normal_leaf": "healthy"}),
    "banana_lsd": ("Banana", "BananaLSD (Mendeley Data)", "https://data.mendeley.com/datasets/9tb7k297ff",
                   {"sigatoka": "banana_sigatoka", "cordana": "banana_cordana",
                    "pestalotiopsis": "banana_pestalotiopsis", "healthy": "healthy"}),
    "sugarcane": ("Sugarcane", "Sugarcane Leaf Disease Dataset (Mendeley Data)", "https://data.mendeley.com/datasets/9424skmnrk",
                  {"redrot": "cane_red_rot", "rust": "cane_rust", "mosaic": "cane_mosaic",
                   "yellow": "cane_yellow_leaf", "healthy": "healthy"}),
    "maize_mld": ("Maize", "MLD maize leaf disease (Mendeley Data)", "https://data.mendeley.com/datasets/3myfctrgk3",
                  {"fall_armyworm": "maize_fall_armyworm", "gray_spot": "maize_gray_leaf_spot",
                   "leaf_blight": "maize_leaf_blight", "healthy": "healthy"}),
    "coconut": ("Coconut", "Coconut Tree Disease Dataset (Mendeley Data)", "https://data.mendeley.com/datasets/gh56wbsnj5/1",
                {"gray_leaf_spot": "coconut_gray_leaf_spot", "bud_rot": "coconut_bud_rot", "leaf_rot": "coconut_leaf_rot",
                 "healthy": "healthy"}),
    # Added crops. Hugging Face (Project-AgML) copies of public Mendeley datasets: groundnut, chilli, blackgram, turmeric are CC BY 4.0,
    # cotton is CC BY-NC 4.0 (non-commercial). Classes with no verified TNAU control in our knowledge base are left out on purpose.
    "groundnut_leaf": ("Groundnut", "Groundnut plant leaf images, Aishwarya et al. 2023 (Mendeley Data, CC BY 4.0)", "https://data.mendeley.com/datasets/22p2vcbxfk/3",
                       {"early_leaf_spot": "groundnut_leaf_spot", "late_leaf_spot": "groundnut_leaf_spot", "rust": "groundnut_rust", "healthy_leaf": "healthy"}),
    "cotton_leaf": ("Cotton", "Cotton Leaf Image Dataset for Disease Classification (Mendeley Data, CC BY-NC 4.0: non-commercial)", "https://data.mendeley.com/datasets/t9hgvk2h9p/1",
                    {"alternaria_leaf": "cotton_alternaria_leaf_spot", "bacterial_blight": "cotton_bacterial_blight", "fusarium_wilt": "cotton_wilt", "healthy_leaf": "healthy"}),
    "blackgram_leaf": ("Blackgram", "Blackgram Plant Leaf Disease (BPLD), Talasila et al. 2022 (Mendeley Data, CC BY 4.0)", "https://data.mendeley.com/datasets/zfcv9fmrgv/3",
                       {"yellow_mosaic": "blackgram_yellow_mosaic", "powdery_mildew": "blackgram_powdery_mildew", "healthy": "healthy"}),
    "chilli_leaf": ("Chilli", "COLD chilli leaf disease dataset (Mendeley Data, CC BY 4.0)", "https://huggingface.co/datasets/Project-AgML/COLD_chili_leaf_disease_classification",
                    {"powdery_mildew": "chilli_powdery_mildew", "cercospora": "chilli_leaf_spot", "healthy": "healthy"}),
    "turmeric_leaf": ("Turmeric", "Turmeric plant leaf disease detection (Mendeley Data, CC BY 4.0)", "https://data.mendeley.com/datasets/jtttfbx342/1",
                      {"blotch": "turmeric_leaf_spot", "leaf_spot": "turmeric_leaf_spot", "healthy_leaf": "healthy"}),
}
EXTS = {".jpg", ".jpeg", ".png"}


def norm(name):
    return name.lower().replace(" ", "_").replace("-", "_")


def class_files(src_dir, mapping):
    """class folder name -> files. Skips augmented copies."""
    found = defaultdict(list)
    for p in src_dir.rglob("*"):
        if p.suffix.lower() not in EXTS or any("augment" in part.lower() for part in p.parts):
            continue
        key = norm(p.parent.name)
        if key in mapping:
            found[key].append(p)
    return found


# Representative reference photos shipped with the dummy village (dataset/then_malai/TM-xx).
# Retrieval-only: licence unknown, health and stage NOT verified (several show a stage that disagrees with the
# parcel's dummy stage), so they are never ground truth. TM-07 carries a stock-photo watermark and is skipped.
REF_DIR = ROOT / "dataset" / "then_malai"
REF_SCENES = {  # file: (crop, scene_type, split)
    "TM-01": ("Coconut", "wide_grove", "reference"), "TM-03": ("Rice", "wide_field", "holdout"),
    "TM-04": ("Sugarcane", "wide_field", "reference"), "TM-05": ("Maize", "plant", "reference"),
    "TM-09": ("Rice", "wide_field", "reference"), "TM-10": ("Sugarcane", "wide_field", "reference"),
    "TM-11": ("Maize", "wide_field", "reference"), "TM-13": ("Rice", "panicle_closeup", "reference"),
    "TM-15": ("Sugarcane", "row_view", "reference"), "TM-16": ("Maize", "plant", "reference"),
}


def add_reference_scenes(items, report):
    for name, (crop, scene, split) in REF_SCENES.items():
        src = next((REF_DIR / (name + e) for e in (".jpg", "") if (REF_DIR / (name + e)).exists()), None)
        if not src:
            report.append(f"reference {name}: file missing")
            continue
        dest = OUT / crop.lower() / "field_scene"
        dest.mkdir(parents=True, exist_ok=True)
        fn = f"{crop.lower()}_{name.lower()}_{scene}.jpg"
        if Image:
            im = Image.open(src).convert("RGB")
            im.thumbnail((768, 768))
            im.save(dest / fn, quality=85)
        items.append({"file": f"{crop.lower()}/field_scene/{fn}", "crop": crop, "condition_code": "field_scene",
                      "condition": "Field scene (health/stage unverified)", "split": split,
                      "source": "FarmwiseAI-provided representative reference photo", "source_url": None,
                      "original_file": f"dataset/then_malai/{src.name}", "image_type": scene,
                      "licence": "unknown - confirm with FarmwiseAI before publishing", "watermark": False,
                      "data_source": "provided_reference_unverified"})


def main():
    rnd = random.Random(SEED)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    items, report = [], []
    for folder, (crop, src_name, src_url, mapping) in SOURCES.items():
        src_dir = RAW / folder
        if not src_dir.exists():
            report.append(f"{folder}: NOT PRESENT (skipped)")
            continue
        found = class_files(src_dir, mapping)
        for key, code in mapping.items():
            files = sorted(found.get(key, []))
            if not files:
                report.append(f"{folder}/{key}: no images found")
                continue
            rnd.shuffle(files)
            pick = files[: N_TRAIN + N_HOLDOUT]
            dest = OUT / crop.lower() / code
            dest.mkdir(parents=True, exist_ok=True)
            base = len(list(dest.glob("*.jpg")))          # two source classes can share one issue code
            for i, f in enumerate(pick, start=0):
                split = "holdout" if i >= len(pick) - min(N_HOLDOUT, max(1, len(pick) // 6)) else "train"
                name = f"{code}_{base + i + 1:03d}.jpg"
                try:
                    if Image:
                        im = Image.open(f).convert("RGB")
                        im.thumbnail((768, 768))
                        im.save(dest / name, quality=85)
                    else:
                        shutil.copy(f, dest / name)
                except Exception as e:  # unreadable image: skip
                    report.append(f"skip {f.name}: {e}")
                    continue
                items.append({"file": f"{crop.lower()}/{code}/{name}", "crop": crop, "condition_code": code,
                              "condition": ISSUES[code]["label"], "split": split, "source": src_name,
                              "source_url": src_url, "original_file": str(f.relative_to(RAW)),
                              "image_type": "leaf_closeup_or_field", "data_source": "real_public_dataset"})
    add_reference_scenes(items, report)
    by_code = Counter(i["condition_code"] for i in items)
    uncovered = [c for c, v in ISSUES.items() if v["photo_class"] and c != "healthy" and by_code[c] == 0]
    no_photo = [c for c, v in ISSUES.items() if not v["photo_class"]]
    manifest = {
        "count": len(items), "per_class": dict(by_code), "uncovered_photo_issues": uncovered,
        "no_photo_class_issues": no_photo,
        "note": "Real public datasets. Licences are set by each source page - confirm CC BY terms and cite the "
                "sources in the submission. Holdout images are random, so near-duplicates from one field burst "
                "may straddle train/holdout; do not report them as a clean accuracy figure.",
        "items": items}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(items)} images, {len(by_code)} classes -> {OUT}")
    print("uncovered (no real photos yet):", uncovered)
    print("no photo class by design (nutrient/abiotic):", no_photo)
    for r in report:
        print("  note:", r)


if __name__ == "__main__":
    main()
