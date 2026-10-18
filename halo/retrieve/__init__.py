"""Retrieval methods compared in the M3 ablation: dense, BM25, hybrid (RRF) and hybrid + cross-encoder rerank."""

import time

from halo.ingest.index import all_payloads, open_index, search
from halo.retrieve.bm25 import BM25Index
from halo.retrieve.fusion import rrf

METHODS = ("dense", "bm25", "hybrid", "hybrid_rerank")


class Retriever:
    """Holds the Qdrant client and the BM25 index for one process."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.collection = cfg["retrieve"]["collection"]
        self.client = open_index(cfg)
        self._bm25: BM25Index | None = None

    @property
    def bm25(self) -> BM25Index:
        # ponytail: rebuilt from Qdrant payloads per process (seconds), so it can never drift from the
        # dense index; persist with bm25s save()/load() if API startup time matters (M6).
        if self._bm25 is None:
            chunks = sorted(all_payloads(self.client, self.collection), key=lambda c: (c["paper_id"], c["chunk_idx"]))
            self._bm25 = BM25Index(chunks, self.cfg)
        return self._bm25

    def retrieve(self, query: str, method: str) -> tuple[list[dict], dict]:
        """Ranked candidates (up to k_candidates, best first) and per-stage latency in ms."""
        if method not in METHODS:
            raise ValueError(f"unknown retrieval method {method!r}; choose from {METHODS}")
        r, ms = self.cfg["retrieve"], {}
        k = r["k_candidates"]

        def timed(stage, fn, *args):
            start = time.perf_counter()
            out = fn(*args)
            ms[stage] = round((time.perf_counter() - start) * 1000, 1)
            return out

        # ponytail: dense and BM25 run sequentially; BM25 takes milliseconds, so threading saves ~nothing.
        if method == "dense":
            return timed("dense", search, self.client, self.collection, query, k, self.cfg), ms
        if method == "bm25":
            return timed("bm25", self.bm25.search, query, k), ms
        dense = timed("dense", search, self.client, self.collection, query, k, self.cfg)
        sparse = timed("bm25", self.bm25.search, query, k)
        fused = timed("fuse", lambda: rrf([dense, sparse], r["rrf_k"])[:k])
        if method == "hybrid":
            return fused, ms
        from halo.retrieve.rerank import rerank  # torch import is slow; only pay for it when reranking
        return timed("rerank", rerank, query, fused, self.cfg), ms

    def close(self) -> None:
        self.client.close()
