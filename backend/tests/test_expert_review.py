"""The expert-review queue: reviewed entries must not carry an unresolved 'unsafe' or 'incorrect' verdict. Unreviewed entries are allowed (they are reported), but they are NOT evidence of correctness."""
import json
from pathlib import Path

Q = Path(__file__).resolve().parent / "expert_review_queue.json"


def _items():
    return json.loads(Q.read_text(encoding="utf-8"))["items"] if Q.exists() else []


def test_no_reviewed_answer_is_marked_unsafe_or_incorrect():
    bad = [i["id"] for i in _items() if i.get("verdict") in ("unsafe", "incorrect") and not i.get("resolved")]
    assert not bad, f"expert review found problems that are not resolved: {bad}"


def test_review_status_is_reported_honestly():
    items = _items()
    reviewed = [i for i in items if i.get("verdict")]
    print(f"expert review: {len(reviewed)} of {len(items)} answers reviewed by a person")
    for i in reviewed:
        assert i.get("reviewer") and i.get("review_date"), f"{i['id']} has a verdict without a named reviewer and date"
