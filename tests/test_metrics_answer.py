import pytest

from eval.metrics.abstention import is_abstention
from eval.metrics.answer import answer_scores
from eval.metrics.slices import summarize

SENTINEL = "INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize("text,expected", [
    ("INSUFFICIENT_EVIDENCE", True),
    ("  insufficient_evidence.\n", True),
    ("The context does not say. INSUFFICIENT_EVIDENCE", True),
    ("The method uses BM25.", False),
    ("", False),
])
def test_is_abstention(text, expected):
    assert is_abstention(text, SENTINEL) is expected


def test_answered_question_scores():
    s = answer_scores(abstained=False, faithful="supported", correct="correct")
    assert s == {"abstained": 0.0, "faithful": 1.0, "correct": 1.0, "correct_if_answered": 1.0}


def test_false_abstention_counts_as_incorrect_and_is_not_faithfulness_scored():
    s = answer_scores(abstained=True, faithful=None, correct=None)
    assert s == {"abstained": 1.0, "faithful": None, "correct": 0.0, "correct_if_answered": None}


def test_unsupported_wrong_answer():
    s = answer_scores(abstained=False, faithful="unsupported", correct="incorrect")
    assert s == {"abstained": 0.0, "faithful": 0.0, "correct": 0.0, "correct_if_answered": 0.0}


def test_judge_failure_is_missing_not_zero():
    s = answer_scores(abstained=False, faithful=None, correct="correct")
    assert s["faithful"] is None and s["correct"] == 1.0


def test_summarize_overall_and_slices_skip_missing_values():
    recs = [
        {"type": "extractive", "source": "text", "m": 1.0},
        {"type": "extractive", "source": "text-image", "m": 0.0},
        {"type": "abstractive", "source": "text", "m": None},
        {"type": "abstractive", "source": "text", "m": 0.5},
    ]
    out = summarize(recs, ["m"])
    assert out["overall"]["m"] == {"mean": 0.5, "n": 3}
    assert out["by_type"]["extractive"]["m"] == {"mean": 0.5, "n": 2}
    assert out["by_type"]["abstractive"]["m"] == {"mean": 0.5, "n": 1}
    assert out["by_modality"]["text"]["m"] == {"mean": 0.75, "n": 2}
    assert out["by_modality"]["text-image"]["m"] == {"mean": 0.0, "n": 1}


def test_summarize_all_missing_gives_none_mean():
    out = summarize([{"type": "a", "source": "text", "m": None}], ["m"])
    assert out["overall"]["m"] == {"mean": None, "n": 0}
