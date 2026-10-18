import pytest

from halo.retrieve.fusion import rrf


def h(paper: str, idx: int) -> dict:
    return {"paper_id": paper, "chunk_idx": idx, "score": 0.0}


def test_rrf_scores_sum_reciprocal_ranks():
    fused = rrf([[h("a", 0), h("b", 0)], [h("b", 0), h("c", 0)]], k=60)
    scores = {f["paper_id"]: f["score"] for f in fused}
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["a"] == pytest.approx(1 / 61)
    assert scores["c"] == pytest.approx(1 / 62)
    assert [f["paper_id"] for f in fused] == ["b", "a", "c"]


def test_rrf_ties_break_on_chunk_key():
    fused = rrf([[h("z", 1)], [h("a", 2)]], k=60)
    assert [(f["paper_id"], f["chunk_idx"]) for f in fused] == [("a", 2), ("z", 1)]


def test_rrf_same_paper_different_chunks_are_distinct():
    assert len(rrf([[h("a", 0), h("a", 1)]], k=60)) == 2


def test_rrf_empty_ranking_is_ignored():
    assert [f["paper_id"] for f in rrf([[h("a", 0)], []], k=60)] == ["a"]
