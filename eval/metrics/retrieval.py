"""Retrieval metrics against qrels (DECISIONS.md D16).

Open RAG Bench has exactly one relevant section per question. The ranking is the chunk list the
retriever returns; a chunk is relevant if its (paper_id, section_id) is the gold section. Only the first
gold chunk counts, so every query has a single relevant item: recall@k is hit@k, and nDCG@k reduces
to 1/log2(rank + 1) because the ideal DCG is 1.
"""

import math

Section = tuple[str, int]


def gold_rank(ranked: list[Section], gold: Section) -> int | None:
    """1-based rank of the first chunk from the gold section, or None if it was not retrieved."""
    return next((i for i, s in enumerate(ranked, 1) if s == gold), None)


def recall_at_k(rank: int | None, k: int) -> float:
    return float(rank is not None and rank <= k)


def reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank


def ndcg_at_k(rank: int | None, k: int) -> float:
    return 1.0 / math.log2(rank + 1) if rank is not None and rank <= k else 0.0


def paper_hit_at_k(ranked: list[Section], gold_paper: str, k: int) -> float:
    """Diagnostic: did any top-k chunk come from the right paper (section ignored)?"""
    return float(any(paper == gold_paper for paper, _ in ranked[:k]))


def query_metrics(ranked: list[Section], gold: Section, ks: tuple[int, ...], ndcg_k: int, paper_k: int) -> dict:
    rank = gold_rank(ranked, gold)
    return {
        **{f"recall@{k}": recall_at_k(rank, k) for k in ks},
        "mrr": reciprocal_rank(rank),
        f"ndcg@{ndcg_k}": ndcg_at_k(rank, ndcg_k),
        f"paper_hit@{paper_k}": paper_hit_at_k(ranked, gold[0], paper_k),
        "gold_rank": rank,
    }
