"""Retrieval evaluation as a regression test. Offline: query embeddings come from tests/retrieval_query_embeddings.npz (refresh with run_retrieval_eval.py --refresh).
The floors below are set just under the measured results, so a change that makes retrieval or the answer/abstain/clarify policy worse fails here."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_retrieval_eval as E  # noqa: E402

from app import config  # noqa: E402


@pytest.fixture(scope="module")
def questions():
    return E.load()


def test_every_answerable_question_has_a_matching_chunk_in_the_knowledge_base(questions):
    chunks = [json.loads(line) for line in open(config.CHUNKS_FILE, encoding="utf-8") if line.strip()]
    for q in questions:
        if q["policy"] == "answer":
            assert any(c["crop"] in q["crops"] and all(re.search(e, c["text"], re.I) for e in q["evidence"]) for c in chunks), f"{q['id']} has no supporting chunk: the dataset drifted from the KB"


def test_dataset_shape(questions):
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids)) and len(questions) >= 130
    assert {q["policy"] for q in questions} == {"answer", "abstain", "clarify", "general", "safety", "answer_card"}
    assert {q["lang"] for q in questions} == {"en", "ta", "tanglish"}
    assert {c for q in questions for c in q["crops"]} >= {"Rice", "Maize", "Banana", "Groundnut", "Sugarcane", "Chilli", "Blackgram"}


@pytest.fixture(scope="module")
def result():
    return E.run(use_hybrid=False, refresh=False)


def test_retrieval_floors(result):
    assert result["hit@5"] >= 0.90 and result["hit@3"] >= 0.85 and result["mrr"] >= 0.80 and result["hit@1"] >= 0.74
    assert result["crop_precision@5"] >= 0.95 and result["citation_complete"] == 1.0


def test_universal_floors(result):
    assert result["general_questions"] >= 30 and result["general_caught_by_word_list"] >= 0.70 and result["safety_banned_name_detected"] == 1.0
    assert result["by_crop_hit@3"]["Cotton"] >= 0.9 and result["by_crop_hit@3"]["Tomato"] >= 0.9


def test_unreadable_chunks_are_never_retrieved():
    from app.steps import retrieve
    retrieve._load_chunks()
    assert retrieve._GARBLED and all(retrieve._CHUNKS[i]["crop"] == "Turmeric" for i in retrieve._GARBLED)


def test_policy_floors(result):
    assert result["clarify_handled"] == 1.0 and result["abstain_handled"] == 1.0 and result["answerable_not_blocked_by_gate"] == 1.0


def test_new_pest_pages_are_found(result):
    new = [d for d in result["detail"] if d["policy"] == "answer" and 45 <= int(d["id"][1:]) <= 52]
    assert len(new) == 8 and all(d["first_relevant_rank"] and d["first_relevant_rank"] <= 3 for d in new)


def test_no_regression_for_chilli_and_blackgram(result):
    assert result["by_crop_hit@3"]["Chilli"] >= 0.95 and result["by_crop_hit@3"]["Blackgram"] >= 0.80 and result["by_crop_hit@3"]["Rice"] >= 0.75


def test_batch_a_crops_are_found(result):
    new = [d for d in result["detail"] if d["policy"] == "answer" and d["id"][0] in "MBT" and d["id"][1:].isdigit()]
    assert len(new) >= 28
    found3 = sum(1 for d in new if d["first_relevant_rank"] and d["first_relevant_rank"] <= 3) / len(new)
    assert found3 >= 0.85, found3


def test_old_questions_did_not_regress_after_batch_a(result):
    old = [d for d in result["detail"] if d["policy"] == "answer" and d["id"][0] in "RU"]
    assert len(old) >= 60
    assert sum(1 for d in old if d["first_relevant_rank"] == 1) / len(old) >= 0.78
    assert sum(1 for d in old if d["first_relevant_rank"] and d["first_relevant_rank"] <= 3) / len(old) >= 0.88
