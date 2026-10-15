import math

import pytest

from eval.metrics.retrieval import gold_rank, ndcg_at_k, paper_hit_at_k, query_metrics, recall_at_k, reciprocal_rank

GOLD = ("p1", 3)


def test_gold_rank_is_one_based_first_match():
    ranked = [("p2", 0), ("p1", 2), ("p1", 3), ("p1", 3)]
    assert gold_rank(ranked, GOLD) == 3


def test_gold_rank_none_when_absent():
    assert gold_rank([("p1", 2), ("p2", 3)], GOLD) is None


def test_recall_at_k_is_hit_at_k():
    assert recall_at_k(5, 5) == 1.0
    assert recall_at_k(6, 5) == 0.0
    assert recall_at_k(None, 10) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank(1) == 1.0
    assert reciprocal_rank(4) == 0.25
    assert reciprocal_rank(None) == 0.0


def test_ndcg_single_relevant_item():
    assert ndcg_at_k(1, 10) == 1.0
    assert ndcg_at_k(3, 10) == pytest.approx(1 / math.log2(4))
    assert ndcg_at_k(11, 10) == 0.0
    assert ndcg_at_k(None, 10) == 0.0


def test_paper_hit_ignores_section():
    ranked = [("p2", 0), ("p1", 9)]
    assert paper_hit_at_k(ranked, "p1", 2) == 1.0
    assert paper_hit_at_k(ranked, "p1", 1) == 0.0


def test_query_metrics_bundle():
    ranked = [("p2", 0), ("p1", 3)] + [("p3", i) for i in range(8)]
    m = query_metrics(ranked, GOLD, ks=(1, 5), ndcg_k=10, paper_k=10)
    assert m == {
        "recall@1": 0.0, "recall@5": 1.0, "mrr": 0.5,
        "ndcg@10": pytest.approx(1 / math.log2(3)), "paper_hit@10": 1.0, "gold_rank": 2,
    }
