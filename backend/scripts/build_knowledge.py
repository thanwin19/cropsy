"""Build the advisory knowledge chunks (RAG corpus) from the official TNAU Crop Production Guides.

Only each crop's own chapter is used (page ranges taken from the guides' tables of contents), so a
"banana" query can never retrieve a redgram page. The auto-extracted pesticide stub table is NOT used;
every dose in a chunk is verbatim source text with its page number.
Output: backend/knowledge/chunks.jsonl, backend/knowledge/sources.json
Run: python backend/scripts/build_knowledge.py
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "dataset" / "knowledge" / "_index" / "pages.jsonl"
OUT = ROOT / "backend" / "knowledge"

AG, HORT = "0c002046_AGRICULTURE.pdf", "d829671c_HORTICULTURE.pdf"
# crop -> [(file, first_pdf_page, last_pdf_page)]
SECTIONS = {
    "Rice": [(AG, 13, 76)],
    "Maize": [(AG, 115, 128)],
    "Sugarcane": [(AG, 297, 319)],
    "Coconut": [(AG, 238, 249), (HORT, 226, 238)],
    "Banana": [(HORT, 21, 27)],
}
# Added later: built after the supplements so chunk order (and the embedding cache) of the first five crops is unchanged.
NEW_SECTIONS = {
    "Groundnut": [(AG, 192, 208)],
    "Cotton": [(AG, 267, 295)],
    "Blackgram": [(AG, 146, 155)],
    "Chilli": [(HORT, 87, 94)],
    "Turmeric": [(HORT, 185, 187)],
}
SOURCES = {
    AG: dict(document_id="DOC_TNAU_AGRON_001", title="Crop Production Guide: Agriculture 2020",
             organization="Tamil Nadu Agricultural University & Directorate of Agriculture", year=2020,
             url="https://agritech.tnau.ac.in/", source_quality="A"),
    HORT: dict(document_id="DOC_TNAU_HORT_002", title="Crop Production Guide: Horticulture 2020",
               organization="Tamil Nadu Agricultural University & Directorate of Horticulture", year=2020,
               url="https://agritech.tnau.ac.in/", source_quality="A"),
}
TOPICS = {
    "variety_season": r"variet|season|cultivar|hybrid",
    "climate_soil": r"climate|rainfall|temperature|soil requirement|soil type",
    "nursery_seed": r"nursery|seed treatment|seedling|sett|sucker|seed rate",
    "planting": r"transplant|planting|sowing|spacing|land preparation|pit",
    "nutrient": r"fertili[sz]er|manure|nutrient|npk|urea|potash|deficien|micronutrient|zinc|fym|basal",
    "irrigation": r"irrigat|water management|drainage|moisture|drip|fertigation",
    "weed": r"weed|herbicide|hoeing",
    "pest": r"pest|insect|borer|weevil|mite|hopper|aphid|larva|caterpillar|armyworm|beetle|ipm",
    "disease": r"disease|blast|blight|rot|spot|wilt|rust|mosaic|fung|bacteri|virus|sigatoka|smut",
    "harvest": r"harvest|yield|maturity|post.?harvest|storage|curing",
}
STAGE_WORDS = {
    "Rice": ["nursery", "transplant", "tillering", "panicle initiation", "booting", "flowering", "milky", "dough", "grain filling", "harvest"],
    "Banana": ["sucker", "vegetative", "flower", "shooting", "bunch", "harvest", "de-suckering", "desuckering"],
    "Sugarcane": ["germination", "tillering", "grand growth", "elongation", "earthing", "maturity", "harvest", "ratoon"],
    "Maize": ["vegetative", "knee", "tasseling", "silking", "grain filling", "maturity", "harvest"],
    "Coconut": ["flowering", "nut", "button", "bearing", "nursery", "seedling", "harvest"],
    "Groundnut": ["sowing", "flowering", "pegging", "pod formation", "pod development", "maturity", "harvest"],
    "Cotton": ["squaring", "flowering", "boll formation", "boll development", "boll opening", "picking", "harvest"],
    "Blackgram": ["vegetative", "flowering", "pod formation", "maturity", "harvest"],
    "Chilli": ["nursery", "transplant", "flowering", "fruit set", "fruiting", "harvest"],
    "Turmeric": ["rhizome", "vegetative", "tillering", "bulking", "maturity", "harvest"],
}
TARGET, MAXC = 900, 1400
DOSE = re.compile(r"\d+(?:\.\d+)?\s*(?:-\s*\d+(?:\.\d+)?\s*)?(?:kg|g|ml|l|lit|litre|ton|tons|t|ppm|%)\s*(?:/|per)\s*(?:ha|acre|l|litre|lit|kg|palm|plant|tree|sq\.?\s*m|m2|10\s*l|ml)", re.I)
HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+)?[A-Z][A-Za-z /&,()\-]{2,70}$")


# Supplementary TNAU Agritech portal pages (public) filling gaps in the printed guides.
# Text is a condensed, faithful extraction; doses are quoted as they appear on the page.
# dose_source: "pdf_text" = read directly from the TNAU PDF; "web_page_via_summarizer" = fetched through a
# summarising tool, so re-check the dose against the URL before the final submission.
PORTAL = "https://agritech.tnau.ac.in/"
SUPPLEMENT = [
    dict(crop="Coconut", topic="disease", issue="coconut_leaf_rot", page="coconut_diseases_6.html",
         url=PORTAL + "crop_protection/coconut_diseases_6.html", dose_source="web_page_via_summarizer",
         text="Coconut leaf rot. Causal organisms: Colletotrichum gloeosporioides, Exserohilum rostratum and Fusarium spp. "
              "Symptoms: water-soaked brown lesions on the spear leaves of root-wilt affected palms; spots enlarge and coalesce "
              "causing extensive rotting; the rotten portions of the lamina dry and are blown off, giving the leaves a fan shape; "
              "in severe cases the spear fails to unfurl. Management: remove the rotten portions from the spear and the two "
              "adjacent leaves. Pour hexaconazole 2 ml or mancozeb 3 g in 300 ml water per palm at the base of the spindle leaf; "
              "2-3 rounds are sufficient for mild infection. Spray crowns and leaves with 1% Bordeaux mixture or 0.5% copper "
              "oxychloride or 0.4% mancozeb in January, April-May and September, taking care to spray the spindle leaf."),
    dict(crop="Sugarcane", topic="disease", issue="cane_mosaic", page="pdf/8.pdf p.32-33",
         url=PORTAL + "pdf/8.pdf", dose_source="pdf_text",
         text="Sugarcane mosaic. Causal organism: Sugarcane mosaic potyvirus. Symptoms: appears prominently on young leaves; "
              "linear chlorotic stripes alternating with dark green areas on the leaves; at later stages yellow stripes appear on "
              "the leaf sheath and stalk. The virus is transmitted by setts and by the aphid Rhopalosiphum maidis. General "
              "management (TNAU): select healthy setts for planting; in the seed crop select plants that do not show symptoms of "
              "red rot, smut, grassy shoot and ratoon stunting; reject setts showing red colour at the cut end and hollows and burn "
              "them. The source gives no mosaic-specific chemical dose."),
    dict(crop="Sugarcane", topic="disease", issue="cane_ratoon_stunting", page="sugarcane_diseases/sugarcane_d5.html",
         url=PORTAL + "crop_protection/sugarcane_diseases/sugarcane_d5.html", dose_source="web_page_via_summarizer",
         text="Ratoon stunting disease of sugarcane. Causal organism: Leifsonia xyli subsp. xyli. Symptoms: stunted plants, most "
              "severe in stubble and ratoon crops; pin-head orange dots of bacteria on the internal soft tissue at the nodes; poor "
              "germination of setts from diseased plants. Management: select disease-free setts and keep field sanitation; treat "
              "setts with hot water at 50 C for about 2 hours; aerated steam therapy; disinfect cutting knives (Lysol, Dettol, "
              "ethanol), with at least 5 minutes of contact."),
    dict(crop="Maize", topic="disease", issue="maize_leaf_blight", page="maize_disease_new/maize_2.html",
         url=PORTAL + "crop_protection/maize_disease_new/maize_2.html", dose_source="web_page_via_summarizer",
         text="Maize leaf blight. Causal organisms: Exserohilum turcicum and Helminthosporium maydis. Symptoms: long cigar-shaped "
              "grey-green to tan lesions on lower leaves, slender and oblong, 1 to 6 inches, running parallel to the leaf margin; "
              "lesions coalesce and can cover the whole leaf; infected leaves turn greyish-green and brittle. Management: burn or "
              "bury infected maize stubble; spray mancozeb or zineb at 2-4 g/l or propiconazole 25% EC at 1 ml/l at 35 and 50 DAS."),
    dict(crop="Maize", topic="disease", issue="maize_common_rust", page="maize_disease_new/maize_4.html",
         url=PORTAL + "crop_protection/maize_disease_new/maize_4.html", dose_source="web_page_via_summarizer",
         text="Maize common rust. Causal organism: Puccinia sorghi. Symptoms: minute flecks on both leaf sides, then circular to "
              "elongate cinnamon-brown powdery pustules on both surfaces; brownish-black pustules as the crop matures. Management: "
              "remove alternate host plants; collect crop remains and destroy by burning or burying; foliar spray at 35 and 50 DAS "
              "with kresoxim-methyl 44.3% SC at 1 ml/l, or tebuconazole at 1 ml/l, or chlorothalonil or mancozeb at 2 ml/l."),
    dict(crop="Maize", topic="disease", issue="maize_brown_spot", page="maize_disease/maize_7.html",
         url=PORTAL + "crop_protection/maize_disease/maize_7.html", dose_source="web_page_via_summarizer",
         text="Maize brown spot. Causal organism: Physoderma maydis. Symptoms: small chlorotic spots in alternate bands of diseased "
              "and healthy tissue on leaf blades; circular dark brown spots on the mid-rib; brown lesions on nodes and internodes that "
              "can cause stalk rotting and lodging in severe infection. Management: early planting to escape infection; remove "
              "Saccharum spontaneum grass around the crop; systemic fungicides based on acylalanines such as metalaxyl (no dose given); "
              "resistant varieties include Ganga 11, Deccan, Deccan 103, Composite Suwan 1, F-9572 A, JKMH-178-4 and FH-3113."),
    dict(crop="Maize", topic="disease", issue="maize_charcoal_rot", page="maize_disease_new/maize_3.html",
         url=PORTAL + "crop_protection/maize_disease_new/maize_3.html", dose_source="web_page_via_summarizer",
         text="Maize charcoal rot. Causal organism: Macrophomina phaseolina. Symptoms: wilting; spread to the lower stalk internodes "
              "as plants mature; premature ripening, shredding and breaking at the crown; greyish streaks on stalks; shredded pith "
              "with minute greyish-black sclerotia on the vascular bundles. Management: crop rotation; avoid water stress at "
              "flowering; prevent nutrient deficiencies; apply potash at 80 kg/ha in endemic areas; soil treatment with "
              "P. fluorescens or T. viride at 2.5 kg/ha with 50 kg well-decomposed FYM at 30 days after sowing."),
]


def is_heading(l):
    if len(l) < 4 or l.endswith((",", ")", "(")) or re.search(r"\d\s*(%|kg|g|ml)|K2O|N2O|P2O5|TNAU", l):
        return False
    return (l.isupper() and len(l) < 70) or bool(re.match(r"^\d+(?:\.\d+){1,3}\.?\s+[A-Z]", l) and len(l) < 80)


def split_long(para, limit=MAXC):
    if len(para) <= limit:
        return [para]
    out, cur = [], ""
    for sent in re.split(r"(?<=[.;:])\s+", para):
        if cur and len(cur) + len(sent) > limit:
            out.append(cur)
            cur = ""
        cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def quality_ok(text):
    toks = re.findall(r"[A-Za-z]{2,}", text)
    if len(toks) < 15:
        return False
    alpha = sum(c.isalpha() for c in text) / max(1, len(text))
    return len(set(t.lower() for t in toks)) / len(toks) > 0.38 and alpha > 0.62


def clean_page(text):
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and not re.fullmatch(r"[\d\s.,\-–]+", l)]
    paras, cur = [], ""
    for l in lines:
        is_head = is_heading(l)
        if l.startswith(("•", "-", "o ")) or is_head:
            if cur:
                paras.append(cur)
            cur = l
            if is_head:
                paras.append(cur)
                cur = ""
        else:
            cur = f"{cur} {l}".strip()
    if cur:
        paras.append(cur)
    return paras


def topics_of(text):
    low = text.lower()
    scores = {t: len(re.findall(p, low)) for t, p in TOPICS.items()}
    ranked = [t for t, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0]
    return ranked[:3] or ["general"]


def build_sections(sections, pages, chunks):
    for crop, secs in sections.items():
        n = 0
        for fname, lo, hi in secs:
            src = SOURCES[fname]
            heading = ""
            buf, buf_page = "", lo

            def flush():
                nonlocal buf, n
                text = buf.strip()
                if len(text) < 120 or not quality_ok(text):
                    buf = ""
                    return
                n += 1
                low = text.lower()
                chunks.append({
                    "chunk_id": f"{crop.lower()}-{src['document_id'][-3:]}-p{buf_page}-{n:03d}",
                    "crop": crop, "text": text, "section": heading, "topics": topics_of(heading + " " + text),
                    "stages": [s for s in STAGE_WORDS[crop] if s in low],
                    "has_dose": bool(DOSE.search(text)),
                    "document_id": src["document_id"], "title": src["title"], "organization": src["organization"],
                    "year": src["year"], "page": buf_page, "source_file": fname,
                    "source_quality": src["source_quality"], "dose_source": "verbatim_source_text",
                })
                buf = ""

            for pg in range(lo, hi + 1):
                p = pages.get((fname, pg))
                if not p:
                    continue
                for para in (q for raw in clean_page(p["text"]) for q in ([raw] if is_heading(raw) else split_long(raw))):
                    if is_heading(para):
                        flush()
                        heading = para.strip()
                        buf_page = pg
                        continue
                    if not buf:
                        buf_page = pg
                    if len(buf) + len(para) > MAXC or (len(buf) >= TARGET):
                        flush()
                        buf_page = pg
                    buf = f"{buf}\n{para}".strip()
            flush()


def main():
    pages = {}
    for line in open(PAGES, encoding="utf-8"):
        p = json.loads(line)
        pages[(p["file"], p["page"])] = p
    OUT.mkdir(parents=True, exist_ok=True)
    chunks = []
    build_sections(SECTIONS, pages, chunks)
    for k, sp in enumerate(SUPPLEMENT, 1):
        crop = sp["crop"]
        chunks.append({
            "chunk_id": f"{crop.lower()}-web-{k:02d}", "crop": crop, "text": sp["text"], "section": sp["issue"],
            "topics": [sp["topic"]], "stages": [], "has_dose": bool(DOSE.search(sp["text"])),
            "document_id": "WEB_TNAU_AGRITECH", "title": f"TNAU Agritech portal - {sp['page']}",
            "organization": "Tamil Nadu Agricultural University", "year": 2026, "page": sp["page"],
            "source_file": sp["url"], "source_quality": "A-web", "dose_source": sp["dose_source"],
            "issue_code": sp["issue"],
        })
    build_sections(NEW_SECTIONS, pages, chunks)
    with open(OUT / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    (OUT / "sources.json").write_text(json.dumps(list(SOURCES.values()), indent=2), encoding="utf-8")
    print(f"{len(chunks)} chunks (incl. {len(SUPPLEMENT)} portal supplements) | avg {sum(len(c['text']) for c in chunks)//len(chunks)} chars")
    print("by crop:", dict(Counter(c["crop"] for c in chunks)))
    print("by topic:", dict(Counter(t for c in chunks for t in c["topics"][:1])))
    print("with dose:", sum(c["has_dose"] for c in chunks))


if __name__ == "__main__":
    main()
