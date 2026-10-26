"""coverage_audit.py: what the knowledge base actually covers, by crop, topic, source and region. Read-only; writes tests/coverage_audit.json.

Topic labels come from the chunk's own 'topics' field (assigned at ingestion by keyword rules in build_knowledge.topics_of), so they are indicative, not a human classification.
A topic is reported 'thin' below 3 chunks and 'none' at 0. The region of every source is 'Tamil Nadu' (TNAU) or 'India (national)' (Spices Board, ICAR-IISR): no source
in the knowledge base covers another state. Usage: python scripts/coverage_audit.py"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

TOPICS = ["climate_soil", "variety_season", "planting", "nursery_seed", "nutrient", "irrigation", "weed", "pest", "disease", "harvest", "general"]   # the labels the ingestion rules assign (build_knowledge.TOPICS)
GROUPS = {"Rice": "cereal", "Maize": "cereal", "Sugarcane": "cash crop", "Cotton": "fibre", "Coconut": "plantation", "Banana": "fruit", "Groundnut": "oilseed", "Blackgram": "pulse",
          "Chilli": "vegetable/spice", "Turmeric": "spice", "Tomato": "vegetable"}
NOT_COVERED = {"cereals and millets": "wheat, sorghum (cholam), pearl millet (cumbu), finger millet (ragi), minor millets",
               "pulses": "redgram, greengram, bengalgram, cowpea, horsegram", "oilseeds": "sunflower, gingelly (sesame), castor, soybean, mustard",
               "vegetables": "brinjal, bhendi, onion, cabbage, cauliflower, carrot, beans, cucurbits, potato (tomato has only a few chunks)",
               "fruits": "mango, guava, papaya, sapota, citrus, pomegranate, grapes, jackfruit", "plantation and spices": "cashew, arecanut, tea, coffee, rubber, pepper, cardamom, ginger",
               "other": "flowers, fodder crops, tobacco, jute, medicinal plants, mushrooms, livestock, fisheries, beekeeping"}


def main() -> None:
    chunks = [json.loads(l) for l in open(config.CHUNKS_FILE, encoding="utf-8") if l.strip()]
    topics = defaultdict(Counter)
    docs = defaultdict(Counter)
    quality = defaultdict(Counter)
    for c in chunks:
        crop = c["crop"]
        t = c.get("topics")
        if isinstance(t, str):
            try:
                t = json.loads(t.replace("'", '"'))
            except ValueError:
                t = [t]
        for k in (t or ["other"])[:3]:
            topics[crop][k] += 1
        docs[crop][c.get("document_id", "?")] += 1
        quality[crop][c.get("source_quality", "?")] += 1
        report = {"total_chunks": len(chunks), "crops": {}, "not_covered_at_all": NOT_COVERED, "regions": {"Tamil Nadu (TNAU)": "all crop guides", "India (national)": "Spices Board turmeric PDF; no other state is covered"}}
    print(f"{len(chunks)} chunks, {len(topics)} crops\n")
    print(f"{'crop':10s} {'group':16s} {'chunks':>6s}  " + " ".join(f"{t[:9]:>9s}" for t in TOPICS))
    for crop in sorted(topics, key=lambda c: -sum(topics[c].values())):
        n = sum(1 for c in chunks if c["crop"] == crop)
        row = [topics[crop].get(t, 0) for t in TOPICS]
        gaps = [t for t, v in zip(TOPICS, row) if v == 0 and t not in ("general",)]
        thin = [t for t, v in zip(TOPICS, row) if 0 < v < 3 and t not in ("general",)]
        report["crops"][crop] = {"group": GROUPS.get(crop, "?"), "chunks": n, "topics": dict(topics[crop]), "documents": dict(docs[crop]), "quality": dict(quality[crop]),
                                 "no_chunks_on": gaps, "thin_on": thin}
        print(f"{crop:10s} {GROUPS.get(crop, '?'):16s} {n:6d}  " + " ".join(f"{v:9d}" for v in row))
    print("\nTopics with NO chunks:")
    for crop, r in report["crops"].items():
        if r["no_chunks_on"]:
            print(f"  {crop:10s} {', '.join(r['no_chunks_on'])}")
    print("\nThin (1-2 chunks):")
    for crop, r in report["crops"].items():
        if r["thin_on"]:
            print(f"  {crop:10s} {', '.join(r['thin_on'])}")
    print("\nNot in the knowledge base at all:")
    for g, items in NOT_COVERED.items():
        print(f"  {g:22s} {items}")
    print("\nRegions: every source is Tamil Nadu (TNAU) except one national PDF (Spices Board / ICAR-IISR, turmeric). No other state is covered.")
    out = Path(__file__).resolve().parent.parent / "tests" / "coverage_audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
