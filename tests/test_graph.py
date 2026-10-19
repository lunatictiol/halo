import pytest

from halo.graph.pipeline import build_graph, route_after_grade


@pytest.mark.parametrize("verdict,attempts,expected", [
    ("sufficient", 1, "generate"),
    ("sufficient", 3, "generate"),      # sufficient on the last attempt still answers
    ("insufficient", 1, "rewrite"),
    ("insufficient", 2, "rewrite"),
    ("insufficient", 3, "abstain"),     # 1 attempt + 2 retries used up
    (None, 1, "rewrite"),               # grader parse error counts as insufficient
    (None, 3, "abstain"),
])
def test_route_after_grade(verdict, attempts, expected):
    assert route_after_grade({"grade": {"verdict": verdict}, "attempts": attempts}, max_retries=2) == expected


def _stub_nodes(sufficient_on_attempt: int | None) -> dict:
    """Grader says sufficient on the given attempt (None: never)."""
    return {
        "retrieve": lambda s: ({"query": s.get("query") or s["question"], "tried": [s.get("query") or s["question"]],
                                "attempts": s.get("attempts", 0) + 1, "candidates": []}, {}),
        "rerank": lambda s: ({"hits": []}, {}),
        "grade": lambda s: ({"grade": {"verdict": "sufficient" if s["attempts"] == sufficient_on_attempt
                                       else "insufficient", "reason": "missing X"}}, {}),
        "rewrite": lambda s: ({"query": f"rewrite {s['attempts']}"}, {}),
        "generate": lambda s: ({"answer": "42", "abstained": False}, {}),
        "abstain": lambda s: ({"answer": "INSUFFICIENT_EVIDENCE: missing X", "abstained": True,
                               "abstain_reason": s["grade"]["reason"]}, {}),
    }


def _nodes_run(out: dict) -> list[str]:
    return [t["node"] for t in out["trace"]]


@pytest.mark.parametrize("max_retries", [0, 1, 2])
def test_never_sufficient_stops_at_retry_limit_and_abstains(max_retries):
    out = build_graph(_stub_nodes(None), max_retries).invoke({"question": "q"})
    assert _nodes_run(out).count("retrieve") == max_retries + 1
    assert _nodes_run(out).count("rewrite") == max_retries
    assert _nodes_run(out)[-1] == "abstain"
    assert out["abstained"] and out["abstain_reason"] == "missing X"


def test_rescued_on_retry_answers_from_rewritten_query():
    out = build_graph(_stub_nodes(sufficient_on_attempt=2), max_retries=2).invoke({"question": "q"})
    assert _nodes_run(out) == ["retrieve", "rerank", "grade", "rewrite", "retrieve", "rerank", "grade", "generate"]
    assert out["tried"] == ["q", "rewrite 1"]
    assert out["question"] == "q" and out["answer"] == "42" and not out["abstained"]


def test_sufficient_first_try_skips_rewrite():
    out = build_graph(_stub_nodes(sufficient_on_attempt=1), max_retries=2).invoke({"question": "q"})
    assert _nodes_run(out) == ["retrieve", "rerank", "grade", "generate"]
    assert all("ms" in t for t in out["trace"])
