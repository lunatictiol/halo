"""BM25 over exactly the chunks in the dense index (DECISIONS.md D21)."""

import bm25s
import Stemmer


class BM25Index:
    def __init__(self, chunks: list[dict], cfg: dict):
        b = cfg["bm25"]
        self.chunks = chunks
        self._stemmer = Stemmer.Stemmer(b["stemmer"])
        self._stopwords = b["stopwords"]
        self._bm25 = bm25s.BM25(k1=b["k1"], b=b["b"])
        self._bm25.index(self.tokenize([c["text"] for c in chunks]), show_progress=False)

    def tokenize(self, texts: list[str]) -> list[list[str]]:
        return bm25s.tokenize(texts, stopwords=self._stopwords, stemmer=self._stemmer,
                              return_ids=False, show_progress=False)

    def search(self, query: str, k: int) -> list[dict]:
        """Top-k chunks with a positive score (zero-score chunks share no term with the query)."""
        tokens = self.tokenize([query])
        if not tokens[0]:
            return []
        idx, scores = self._bm25.retrieve(tokens, k=min(k, len(self.chunks)), show_progress=False)
        return [{**self.chunks[i], "score": float(s)} for i, s in zip(idx[0], scores[0]) if s > 0]
