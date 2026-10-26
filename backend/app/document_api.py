"""document_api.py: read a photographed or scanned document (land record, soil-test card, advisory page, any PDF) and return its text.

How the text is read:
  * a PDF with its own text layer: the text is taken directly (free, instant), every page;
  * a photo, or a scanned PDF page: Amazon Textract reads it (good for English and numbers), and Ministral 3 8B (a model that can look at images)
    reads the same picture. If the Ministral reading contains Tamil script, it is used, because Textract does not read Tamil script (it returns nonsense for it).
Capped per server run to protect AWS credit. The text is returned for the farmer to see; nothing is stored."""
from __future__ import annotations

import base64
import io
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from app import config

router = APIRouter()
CAP = int(os.getenv("CROPSY_DOC_MAX", "60"))                 # documents per server run
MAX_BYTES = int(os.getenv("CROPSY_DOC_MAX_MB", "25")) * 1024 * 1024
MAX_PAGES = int(os.getenv("CROPSY_DOC_MAX_PAGES", "300"))    # a safety stop, not a practical limit
OK_TYPES = ("image/png", "image/jpeg", "application/pdf", "image/tiff")
NL = chr(10)
_used = {"n": 0}
_lock = threading.Lock()
_TAMIL = re.compile(r"[஀-௿]")

OCR_PROMPT = ("Transcribe all the text in this image exactly as written, line by line, keeping numbers exactly. The text may be Tamil, English or both. "
              "Output only the text, with no comment.")


def _textract(png_or_jpg: bytes) -> tuple[str, float | None]:
    from app import aws_resources
    tx = aws_resources.session().client("textract")                     # the SSO profile on a laptop, the service role when deployed
    r = tx.detect_document_text(Document={"Bytes": png_or_jpg})
    lines = [b for b in r.get("Blocks", []) if b.get("BlockType") == "LINE"]
    conf = [b.get("Confidence", 0) for b in lines]
    return NL.join(b["Text"] for b in lines), (round(sum(conf) / len(conf), 1) if conf else None)


def _vision_text(img: bytes, fmt: str) -> str:
    """Ministral 3 8B looks at the picture and transcribes it (reads Tamil script; Textract cannot)."""
    from app import aws_resources
    c = aws_resources.session().client("bedrock-runtime")
    r = c.converse(modelId=config.MODEL_MINISTRAL_8B, messages=[{"role": "user", "content": [{"image": {"format": fmt, "source": {"bytes": img}}}, {"text": OCR_PROMPT}]}],
                   inferenceConfig={"maxTokens": 2000, "temperature": 0})
    return r["output"]["message"]["content"][0]["text"].strip()


def _read_picture(img: bytes, fmt: str) -> tuple[str, str, float | None]:
    """One picture or scanned page -> (text, how, textract_confidence). Textract for English, Ministral vision when the page has Tamil."""
    t_text, conf, err = "", None, ""
    try:
        t_text, conf = _textract(img)
    except Exception as e:  # noqa: BLE001
        err = str(e)
    v_text = ""
    try:
        v_text = _vision_text(img, fmt)
    except Exception:  # noqa: BLE001
        pass
    if len(_TAMIL.findall(v_text)) >= 10:
        return v_text, "Ministral vision (Tamil)", conf
    if t_text.strip():
        return t_text, "Amazon Textract", conf
    if v_text.strip():
        return v_text, "Ministral vision", conf
    if "UnsupportedDocument" in err:
        raise HTTPException(status_code=422, detail="This file could not be read. Use a clear photo or a PDF.")
    raise HTTPException(status_code=422, detail="No readable text was found in this picture.")


@router.post("/api/document")
def read_document(payload: dict):
    data_url = str(payload.get("data_url", ""))
    if not data_url.startswith("data:") or "," not in data_url:
        raise HTTPException(status_code=422, detail="send the file as a base64 data URL")
    head, b64 = data_url.split(",", 1)
    mime = head[5:].split(";")[0].lower()
    if mime not in OK_TYPES:
        raise HTTPException(status_code=415, detail="Only a photo (JPG, PNG), a PDF or a TIFF can be read.")
    raw = base64.b64decode(b64)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    with _lock:
        if _used["n"] >= CAP:
            raise HTTPException(status_code=429, detail=f"Document limit ({CAP} per run) reached, to protect AWS credit.")
        _used["n"] += 1
    if mime == "application/pdf":
        return _read_pdf(raw)
    text, how, conf = _read_picture(raw, "png" if mime == "image/png" else "jpeg")
    return {"text": text, "lines": text.count(NL) + 1, "mean_confidence": conf, "how": how, "note": f"Read by {how}. Check the numbers against your document before relying on them."}


def _read_pdf(raw: bytes) -> dict:
    """Any length. Pages with their own text are read directly; pages that are only pictures are drawn and read as pictures (in parallel)."""
    try:
        import pymupdf
        doc = pymupdf.open(stream=raw, filetype="pdf")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"This PDF could not be opened: {str(e)[:80]}")
    total = len(doc)
    n = min(total, MAX_PAGES)
    texts = [(doc[i].get_text() or "").strip() for i in range(n)]
    todo = [i for i, t in enumerate(texts) if len(t) < 25]            # pages with no text layer: scans
    hows: set[str] = set()
    if not todo or len(todo) < n:
        hows.add("text inside the PDF")
    if todo:
        images = [(i, doc[i].get_pixmap(dpi=150).tobytes("png")) for i in todo]   # draw first (pymupdf is not thread-safe), read in parallel
        def read(item):
            i, png = item
            try:
                return i, _read_picture(png, "png")
            except HTTPException:
                return i, ("", "", None)
        with ThreadPoolExecutor(max_workers=4) as ex:
            for i, (t, how, _c) in ex.map(read, images):
                texts[i] = t
                if how:
                    hows.add(how)
    text = (NL + NL).join(f"[page {i + 1}] {t}" for i, t in enumerate(texts) if t)
    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable text was found in this PDF.")
    return {"text": text, "lines": text.count(NL) + 1, "mean_confidence": None, "pages_read": n, "pages_total": total,
            "note": f"Read {n} of {total} pages by {', '.join(sorted(hows))}. Check the details against your document."}
