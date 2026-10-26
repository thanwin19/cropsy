"""
test_models.py — Test-call all 6 Bedrock models and print which are usable.
Writes backend/cache/model_status.json.
Usage: python scripts/test_models.py
"""
import json
import sys
from pathlib import Path

# Add parent dir to path so we can import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.models import bedrock

MODELS = [
    config.MODEL_NOVA_MICRO,
    config.MODEL_NOVA_LITE,
    config.MODEL_MINISTRAL_3B,
    config.MODEL_MINISTRAL_8B,
    config.MODEL_TITAN_TEXT,
    config.MODEL_TITAN_MULTIMODAL,
]


def main():
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for model_id in MODELS:
        print(f"Testing {model_id} ...", end=" ", flush=True)
        result = bedrock.probe_model(model_id)
        status = result.get("status", "?")
        if status == "ok":
            extra = f"dim={result.get('dim')} latency={result.get('latency_ms')}ms tokens={result.get('tokens')}"
            print(f"OK  {extra}")
        else:
            print(f"UNAVAILABLE  {result.get('error', '')}")
        results.append(result)

    out_file = config.MODEL_STATUS_FILE
    out_file.write_text(json.dumps(results, indent=2))
    print(f"\nStatus written to {out_file}")

    usable = [r["model_id"] for r in results if r["status"] == "ok"]
    unavailable = [r["model_id"] for r in results if r["status"] != "ok"]
    print(f"\nUsable ({len(usable)}): {usable}")
    if unavailable:
        print(f"Unavailable ({len(unavailable)}): {unavailable}")
        print("Router will degrade automatically for unavailable models.")


if __name__ == "__main__":
    main()
