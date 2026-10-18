"""Reciprocal Rank Fusion (Cormack et al., 2009): score(d) = sum over rankings of 1 / (k + rank(d)).

Rank-based, so dense cosine scores and BM25 scores never need to be put on a common scale.
"""


def chunk_key(hit: dict) -> tuple[str, int]:
    return hit["paper_id"], hit["chunk_idx"]


def rrf(rankings: list[list[dict]], k: int) -> list[dict]:
    """Fuse ranked hit lists into one, best first. Ties break on chunk key so the order is deterministic."""
    scores: dict[tuple[str, int], float] = {}
    hits: dict[tuple[str, int], dict] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, 1):
            key = chunk_key(hit)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            hits.setdefault(key, hit)
    order = sorted(scores, key=lambda key: (-scores[key], key))
    return [{**hits[key], "score": scores[key]} for key in order]
