"""Per-query answer scores from judge verdicts. None means "not applicable or judge failed" and is
excluded from means, never counted as 0 (DECISIONS.md D17)."""

POSITIVE = {"supported", "correct"}


def _score(verdict: str | None) -> float | None:
    return None if verdict is None else float(verdict in POSITIVE)


def answer_scores(abstained: bool, faithful: str | None, correct: str | None) -> dict:
    """faithful/correct are judge verdict labels (or None). An abstention on an answerable question is a
    wrong answer for `correct`, and has no claims to check for `faithful`."""
    if abstained:
        return {"abstained": 1.0, "faithful": None, "correct": 0.0, "correct_if_answered": None}
    c = _score(correct)
    return {"abstained": 0.0, "faithful": _score(faithful), "correct": c, "correct_if_answered": c}
