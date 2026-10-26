"""build_video_catalog.py: build data/videos.json, a catalog of REAL educational videos from TNAU TV (the official Tamil Nadu Agricultural University YouTube channel,
@tnautv2557, linked from tnau.ac.in). Each video is found by searching the channel's own search page for farming topics, then verified with YouTube's oEmbed endpoint
(title, channel name, working). Nothing is invented; a video that fails oEmbed is dropped. Re-run to refresh.   Usage: python scripts/build_video_catalog.py"""
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"
OUT = Path(__file__).resolve().parent.parent / "data" / "videos.json"
CHANNELS = {"@tnautv2557": "tnau", "@ICARIndia": "indian council of agricultural research"}      # official channels, each linked from its own organisation website (tnau.ac.in, icar.org.in)
TOPICS = ["rice", "paddy", "SRI", "sugarcane", "banana", "coconut", "groundnut", "cotton", "maize", "blackgram", "greengram", "redgram", "sesame", "sunflower", "castor", "turmeric",
          "chilli", "tomato", "brinjal", "onion", "okra", "mango", "vermicompost", "compost", "organic farming", "biofertilizer", "panchagavya", "drip irrigation", "sprinkler",
          "water management", "soil testing", "soil health", "nutrient management", "fertilizer", "seed treatment", "nursery", "pest management", "IPM", "disease management",
          "stem borer", "fall armyworm", "whitefly", "pheromone trap", "trichogramma", "biocontrol", "weed management", "harvest", "post harvest", "mushroom", "drone", "mulching",
          "millets", "ragi", "sorghum", "fodder", "integrated farming", "farm pond", "crop insurance", "seed production", "grafting", "micronutrient", "nematode", "farmer success story"]


def search(q: str, channel: str) -> list[tuple[str, str]]:
    h = S.get(f"https://www.youtube.com/{channel}/search", params={"query": q, "hl": "en"}, timeout=30).text
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", h, re.S)
    if not m:
        return []
    d = json.loads(m.group(1))
    out: list[tuple[str, str]] = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO" and "contentId" in o:
                out.append((o["contentId"], o.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content") or ""))
            if "videoRenderer" in o and isinstance(o["videoRenderer"], dict) and o["videoRenderer"].get("videoId"):
                v = o["videoRenderer"]
                out.append((v["videoId"], (v.get("title", {}).get("runs") or [{}])[0].get("text") or ""))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    seen: set[str] = set()
    return [(a, b) for a, b in out if not (a in seen or seen.add(a))]


def oembed(vid: str) -> dict | None:
    try:
        r = S.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"}, timeout=20)
        return r.json() if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    found: dict[str, dict] = {}
    for ch in CHANNELS:
        for t in TOPICS:
            try:
                for vid, title in search(t, ch)[:6]:
                    e = found.setdefault(vid, {"id": vid, "title": title, "queries": []})
                    if t not in e["queries"]:
                        e["queries"].append(t)
            except Exception as ex:  # noqa: BLE001
                print("search failed", ch, t, ex)
            time.sleep(0.4)
    print(len(found), "candidates")
    keep = []
    for vid, e in found.items():
        o = oembed(vid)
        if not o or not any(k in (o.get("author_name") or "").lower() for k in CHANNELS.values()):
            continue                                    # not reachable, or not from the TNAU channel: dropped
        keep.append({"id": vid, "title": o.get("title") or e["title"], "channel": o.get("author_name"), "url": f"https://www.youtube.com/watch?v={vid}",
                     "topics": e["queries"], "verified": str(date.today())})
    OUT.write_text(json.dumps({"source": "TNAU TV (@tnautv2557) and ICAR (@ICARIndia), verified by YouTube oEmbed", "built": str(date.today()), "videos": keep}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(keep), "verified videos written to", OUT)


if __name__ == "__main__":
    sys.exit(main())
