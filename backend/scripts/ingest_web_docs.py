"""Add official public pages and PDFs to the advisory knowledge base for the crops the 2020 guides cover only thinly
(Banana, Turmeric, Chilli, Blackgram). Chunks are appended to backend/knowledge/chunks.jsonl, so the existing embeddings keep
their row order; then run scripts/embed_knowledge.py to embed only the new rows.

Every chunk keeps its URL, organisation, document id and quality grade "B" (web or extension document, not the printed state guide).
Doses are quoted exactly as the source gives them: re-check against the URL before relying on one.
Usage: python backend/scripts/ingest_web_docs.py
"""
import html
import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_knowledge as bk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "knowledge"
RAW = ROOT / "dataset" / "knowledge" / "web"
HEADERS = {"User-Agent": "Mozilla/5.0 CropsyPrototype (research)"}
BANANA = "https://agritech.tnau.ac.in/expert_system/banana/"

SOURCES = {
    "WEB_TNAU_BANANA_ES": dict(title="TNAU Agritech Banana Expert System", organization="Tamil Nadu Agricultural University", year=None, url=BANANA + "index.html"),
    "WEB_TNAU_CHILLI_VAR": dict(title="TNAU Agritech Horticulture: Chilli varieties", organization="Tamil Nadu Agricultural University", year=2023,
                                url="https://agritech.tnau.ac.in/horticulture/horti_vegetables_chilli_variety_K.html"),
    "WEB_TNAU_BLACKGRAM_INT": dict(title="TNAU Agritech: Blackgram intercropping", organization="Tamil Nadu Agricultural University", year=None,
                                   url="https://agritech.tnau.ac.in/agriculture/CropProduction/Pulses/BlackgramIntercropping.html"),
    "PDF_SPICES_TURMERIC": dict(title="Turmeric: Cultivation practices", organization="Spices Board India (ICAR-IISR)", year=None,
                                url="https://www.indianspices.com/sites/default/files/cultivation_practices-TURMERIC-1.pdf"),
}
PAGES = [  # (crop, document id, url, label)
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "season&variety.html", "Season and variety"),
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "plantingmaterial.html", "Planting material"),
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "cultivation.html", "Cultivation"),
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "Nutrientmgmt.html", "Nutrient management"),
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "irrigationmanagement.html", "Irrigation management"),
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "cropprotection.html", "Crop protection"),
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "harvest&post.html", "Harvest and post-harvest"),
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "cli.html", "Climate and soil"),
    ("Banana", "WEB_TNAU_BANANA_ES", BANANA + "botany.html", "Botany"),
    ("Chilli", "WEB_TNAU_CHILLI_VAR", SOURCES["WEB_TNAU_CHILLI_VAR"]["url"], "Varieties"),
    ("Blackgram", "WEB_TNAU_BLACKGRAM_INT", SOURCES["WEB_TNAU_BLACKGRAM_INT"]["url"], "Intercropping"),
]
BOILER = re.compile(r"(^home\b|contact|all rights reserved|mmloadmenus|updated on|photo bank|^back to top|site map|^menu$|copyright|tnau 20\d\d)", re.I)


def html_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|head|nav|footer)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d|table|ul|ol)>", "\n", raw)
    raw = re.sub(r"(?i)</t[dh]>", " | ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = raw.replace("Â", " ").replace(" ", " ")
    raw = re.sub(r"(?i)top of page", " ", raw)
    lines = [re.sub(r"\s+", " ", html.unescape(l)).strip(" |") for l in raw.splitlines()]
    return "\n".join(l for l in lines if l and not BOILER.search(l))


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def pdf_text(url: str, cache: Path) -> str:
    if not cache.exists():
        cache.write_bytes(requests.get(url, headers=HEADERS, timeout=60).content)
    import fitz
    return "\n".join(p.get_text() for p in fitz.open(cache))


def chunks_from(text: str, crop: str, doc_id: str, label: str, url: str, counter: dict) -> list[dict]:
    out, heading, buf = [], label, ""

    def flush():
        nonlocal buf
        t = buf.strip()
        buf = ""
        if len(t) < 140 or not bk.quality_ok(t):
            return
        counter[crop] = counter.get(crop, 0) + 1
        low = t.lower()
        src = SOURCES[doc_id]
        out.append({"chunk_id": f"{crop.lower()}-web-{counter[crop]:03d}", "crop": crop, "text": t, "section": heading, "topics": bk.topics_of(heading + " " + t),
                    "stages": [s for s in bk.STAGE_WORDS[crop] if s in low], "has_dose": bool(bk.DOSE.search(t)), "document_id": doc_id, "title": src["title"],
                    "organization": src["organization"], "year": src["year"], "page": label, "source_file": url, "source_quality": "B", "dose_source": "web_or_extension_text_check_url"})

    for para in bk.clean_page(text):
        if bk.is_heading(para):
            flush()
            heading = para.title()
            continue
        for piece in bk.split_long(para):
            if buf and len(buf) + len(piece) > bk.TARGET:
                flush()
            buf = f"{buf} {piece}".strip()
    flush()
    return out


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    existing = [json.loads(l) for l in open(OUT / "chunks.jsonl", encoding="utf-8") if l.strip()]
    kept = [c for c in existing if c.get("document_id") not in SOURCES]     # re-runnable: drop earlier web chunks, keep order of the rest
    new, counter = [], {}
    for crop, doc, url, label in PAGES:
        try:
            raw = fetch(url)
        except Exception as e:  # noqa: BLE001
            print("SKIP", url, repr(e)[:70])
            continue
        (RAW / (re.sub(r"[^A-Za-z0-9]+", "_", url)[-80:] + ".html")).write_text(raw, encoding="utf-8")
        cs = chunks_from(html_text(raw), crop, doc, label, url, counter)
        print(f"{crop:9s} {label:28s} {len(cs):3d} chunks")
        new += cs
    pdf = pdf_text(SOURCES["PDF_SPICES_TURMERIC"]["url"], RAW / "turmeric_spices_board.pdf")
    cs = chunks_from(pdf, "Turmeric", "PDF_SPICES_TURMERIC", "Cultivation practices", SOURCES["PDF_SPICES_TURMERIC"]["url"], counter)
    print(f"Turmeric  PDF Spices Board              {len(cs):3d} chunks")
    new += cs
    with open(OUT / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in kept + new:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    srcs = [s for s in json.loads((OUT / "sources.json").read_text(encoding="utf-8")) if s["document_id"] not in SOURCES]
    for did, s in SOURCES.items():
        srcs.append({"document_id": did, **s, "source_quality": "B"})
    (OUT / "sources.json").write_text(json.dumps(srcs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"kept {len(kept)} + new {len(new)} = {len(kept) + len(new)} chunks. Next: python backend/scripts/embed_knowledge.py")


if __name__ == "__main__":
    main()
