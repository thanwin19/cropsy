"""Third batch of official TNAU Agritech crop-protection pages: the PEST pages for Chilli (thrips, aphid, cutworm, gram caterpillar, yellow mite) and Blackgram.
The earlier batches covered chilli and blackgram DISEASES; the 2020 guide covers blackgram production and a pest table, but chilli had nothing on sucking pests or mites.

Rules this script follows (same as the earlier batches, plus two safeguards):
  * APPENDS only: existing rows keep their positions, so existing embeddings stay valid. A document id already present is skipped.
  * Duplicate guard: a new chunk whose word-shingles are at least 80% contained in an existing chunk of the same crop is dropped and reported.
  * Source and citation are kept: URL, title, organisation, page label, quality grade B (web/extension page, not the printed state guide).
  * Doses are quoted exactly as the page prints them. They are NOT checked against the pesticide registry; Cropsy's banned/restricted guard still applies at answer time.
  * The TNAU site's TLS certificate has been expired at times. Verification is never disabled. The script retries https; only if https keeps failing does it read the same
    public page over plain http (the site links to itself over http) and it records which scheme was used in the raw copy's name and in the printed log.
Licence: the portal's disclaimer (agritech.tnau.ac.in/disclaimer_en.html) says the information is "provided for information purposes only" and states no open licence.
Cropsy uses it as an attributed retrieval source in a prototype; it must not be redistributed as Cropsy's own content.
Usage: python backend/scripts/ingest_web_docs3.py [--dry-run]    then: python backend/scripts/embed_knowledge.py"""
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest_web_docs as iw  # noqa: E402

CP = "https://agritech.tnau.ac.in/crop_protection/"
SOURCES3 = {
    "WEB_TNAU_CHILLI_PEST": dict(title="TNAU Agritech Crop Protection: Pests of chilli", organization="Tamil Nadu Agricultural University", year=None, url=CP + "crop_prot_crop_insect-veg_chillies.html"),
    "WEB_TNAU_BLACKGRAM_PEST": dict(title="TNAU Agritech Crop Protection: Pests of black and green gram", organization="Tamil Nadu Agricultural University", year=None,
                                    url=CP + "crop_prot_crop_insect_pul_bla%20and%20greenmain.html"),
}
CHILLI = [CP + f"chilli/chilli_{i}.html" for i in range(1, 6)]
BLACK = [CP + f"greenblack/crop_prot_crop_insect_pul_bla_and%20green_{i}.html" for i in (1, 2, 3, 4, 6, 7, 10, 11)]
HEADERS = iw.HEADERS


def get(url: str, tries: int = 6) -> tuple[str, str]:
    """Return (text, scheme). https first with retries (verification on); plain http only if https keeps failing."""
    for scheme_url, scheme in ((url, "https"), (url.replace("https://", "http://"), "http")):
        for _ in range(tries if scheme == "https" else 3):
            try:
                r = requests.get(scheme_url, headers=HEADERS, timeout=30)
                r.raise_for_status()
                return r.text, scheme
            except Exception:  # noqa: BLE001
                time.sleep(1.2)
    raise RuntimeError("could not fetch " + url)


def shingles(t: str, n: int = 5) -> set:
    w = re.findall(r"[a-z0-9]+", t.lower())
    return {" ".join(w[i:i + n]) for i in range(max(1, len(w) - n + 1))}


def contained(new: str, old: str) -> float:
    a = shingles(new)
    return len(a & shingles(old)) / max(1, len(a))


def main() -> None:
    dry = "--dry-run" in sys.argv
    iw.SOURCES.update(SOURCES3)
    out = iw.OUT
    existing = [json.loads(l) for l in open(out / "chunks.jsonl", encoding="utf-8") if l.strip()]
    have = {c.get("document_id") for c in existing}
    counter: dict = {}
    for c in existing:
        m = re.match(r"([a-z]+)-web-(\d+)$", c["chunk_id"])
        if m:
            counter[c["crop"]] = max(counter.get(c["crop"], 0), int(m.group(2)))
    before = len(existing)
    new, dropped = [], []
    for crop, doc, urls in (("Chilli", "WEB_TNAU_CHILLI_PEST", CHILLI), ("Blackgram", "WEB_TNAU_BLACKGRAM_PEST", BLACK)):
        if doc in have:
            print("skip (already present):", doc)
            continue
        same = [c["text"] for c in existing if c["crop"] == crop]
        for u in urls:
            try:
                raw, scheme = get(u)
            except Exception as e:  # noqa: BLE001
                print("SKIP", u, repr(e)[:70])
                continue
            (iw.RAW / (re.sub(r"[^A-Za-z0-9]+", "_", u)[-70:] + f"_{scheme}.html")).write_text(raw, encoding="utf-8")
            text = iw.html_text(raw)
            label = (text.splitlines() or [u])[1][:60] if len(text.splitlines()) > 1 else (text.splitlines() or [u])[0][:60]
            cs = iw.chunks_from(text, crop, doc, label, u, counter)
            kept = []
            for c in cs:
                worst = max((contained(c["text"], o) for o in same), default=0.0)
                (dropped if worst >= 0.8 else kept).append(c if worst < 0.8 else (c["chunk_id"], round(worst, 2)))
            print(f"{crop:9s} {u.rsplit('/', 1)[-1][-38:]:38s} via {scheme:5s} {len(cs)} chunk(s), kept {len(kept)}  | {label}")
            new += [c for c in kept if isinstance(c, dict)]
    print(f"existing chunks: {before}; new chunks kept: {len(new)}; dropped as duplicates: {len(dropped)} {dropped}")
    for c in new:
        print(f"  + {c['chunk_id']:16s} {c['page'][:40]:40s} has_dose={c['has_dose']}  {c['text'][:90]!r}")
    if dry or not new:
        return
    with open(out / "chunks.jsonl", "a", encoding="utf-8") as f:
        for c in new:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    srcs = json.loads((out / "sources.json").read_text(encoding="utf-8"))
    for did, s in SOURCES3.items():
        if not any(x["document_id"] == did for x in srcs):
            srcs.append({"document_id": did, **s, "source_quality": "B"})
    (out / "sources.json").write_text(json.dumps(srcs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"appended {len(new)} chunks ({before} -> {before + len(new)}). Next: python backend/scripts/embed_knowledge.py")


if __name__ == "__main__":
    main()
