"""Second batch of official TNAU Agritech crop-protection pages for the two thinnest crops (Chilli, Blackgram).
Unlike ingest_web_docs.py this only APPENDS new rows (existing rows and their embeddings keep their positions); a document that is already present is skipped.
Then run: python backend/scripts/embed_knowledge.py   (embeds only the new rows)
Doses are quoted exactly as the source page gives them; re-check against the URL before relying on one.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest_web_docs as iw  # noqa: E402

CP = "https://agritech.tnau.ac.in/crop_protection/"
SOURCES2 = {
    "WEB_TNAU_CHILLI_DIS": dict(title="TNAU Agritech Crop Protection: Chilli diseases", organization="Tamil Nadu Agricultural University", year=None, url=CP + "crop_prot_crop%20diseases_veg_chilli.html"),
    "WEB_TNAU_BLACKGRAM_DIS": dict(title="TNAU Agritech Crop Protection: Blackgram diseases", organization="Tamil Nadu Agricultural University", year=None, url=CP + "crop_prot_crop%20diseases_pulses_blackgram.html"),
}
CHILLI = [CP + f"chilli_diseases_{i}.html" for i in range(1, 8)]
BLACK = [CP + "black_gram_disease/" + p for p in ["anthracnose.html", "blackgram_d1.html", "blackgram_d3.html", "blackgram_d4.html", "blackgram_d5.html", "blackgram_d6.html", "blackgram_d8.html", "blackgram_d9.html",
                                                  "cercosporal_leaf_spot.html", "leaf_crinkle.html", "powdery_mildew.html", "root_rot_leafblight.html", "rust.html", "yellow_mosaic.html"]]


def main() -> None:
    iw.SOURCES.update(SOURCES2)
    out = iw.OUT
    existing = [json.loads(l) for l in open(out / "chunks.jsonl", encoding="utf-8") if l.strip()]
    have = {c.get("document_id") for c in existing}
    counter = {}
    for c in existing:                       # continue numbering so chunk ids stay unique
        m = re.match(r"([a-z]+)-web-(\d+)$", c["chunk_id"])
        if m:
            counter[c["crop"]] = max(counter.get(c["crop"], 0), int(m.group(2)))
    new = []
    for crop, doc, urls in (("Chilli", "WEB_TNAU_CHILLI_DIS", CHILLI), ("Blackgram", "WEB_TNAU_BLACKGRAM_DIS", BLACK)):
        if doc in have:
            print("skip (already present):", doc)
            continue
        for u in urls:
            try:
                raw = iw.fetch(u)
            except Exception as e:  # noqa: BLE001
                print("SKIP", u, repr(e)[:70])
                continue
            text = iw.html_text(raw)
            label = (text.splitlines() or [u])[0][:60]
            cs = iw.chunks_from(text, crop, doc, label, u, counter)
            print(f"{crop:9s} {u.rsplit('/', 1)[-1]:32s} {len(cs):3d} chunks")
            new += cs
    if not new:
        return
    with open(out / "chunks.jsonl", "a", encoding="utf-8") as f:
        for c in new:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    srcs = json.loads((out / "sources.json").read_text(encoding="utf-8"))
    for did, s in SOURCES2.items():
        if not any(x["document_id"] == did for x in srcs):
            srcs.append({"document_id": did, **s, "source_quality": "B"})
    (out / "sources.json").write_text(json.dumps(srcs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"appended {len(new)} chunks. Next: python backend/scripts/embed_knowledge.py")


if __name__ == "__main__":
    main()
