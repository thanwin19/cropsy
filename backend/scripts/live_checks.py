"""
live_checks.py: the small, capped set of live AWS checks, in one command (about 5 US cents in all).

   aws sso login --profile FAI-TCE-Builder-AI-402365884845
   python backend/scripts/live_checks.py            # all three
   python backend/scripts/live_checks.py --only caption

  1  caption   tests/eval_caption.py --n 20        photo caption + judge + check on 20 held-out photos
  2  bakeoff   tests/model_bakeoff.py --limit 12   Nova Micro vs Ministral 3B vs Ministral 8B on 12 questions
  3  ecr       tests/eval_ecr.py                   only if an agronomist has filled rationales in tests/expert_rationales.json

It stops at once if the AWS login is not valid, so nothing is spent on a failed run.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACK = HERE.parent
sys.path.insert(0, str(BACK))


def aws_ready() -> bool:
    try:
        from app.models import bedrock
        bedrock.embed_text("ready")
        return True
    except Exception as e:  # noqa: BLE001
        print("AWS is not ready:", repr(e)[:140])
        print("Run:  aws sso login --profile FAI-TCE-Builder-AI-402365884845")
        return False


def run(name: str, args: list[str]) -> None:
    print(f"\n=== {name} ===")
    subprocess.run([sys.executable, *args], cwd=BACK)


def main() -> None:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    if not aws_ready():
        sys.exit(1)
    if only in (None, "caption"):
        run("caption", ["tests/eval_caption.py", "--n", "20"])
    if only in (None, "bakeoff"):
        run("bakeoff", ["tests/model_bakeoff.py", "--limit", "12"])
    if only in (None, "ecr"):
        filled = [k for k, v in json.loads((BACK / "tests" / "expert_rationales.json").read_text(encoding="utf-8"))["items"].items() if v.get("expert_rationale", "").strip()]
        if filled:
            run("ecr", ["tests/eval_ecr.py", "--ids", ",".join(filled[:8])])
        else:
            print("\n=== ecr === skipped: no expert rationales filled in yet (tests/expert_rationales.json)")
    print("\nReports: tests/caption_eval.json, tests/bakeoff_report.json, tests/ecr_report.json")


if __name__ == "__main__":
    main()
