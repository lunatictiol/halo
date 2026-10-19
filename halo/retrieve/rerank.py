"""Cross-encoder reranking: score each (query, chunk) pair jointly, then sort (DECISIONS.md D23)."""

from functools import cache

import torch
from sentence_transformers import CrossEncoder


def _device(setting: str) -> str:
    return ("cuda" if torch.cuda.is_available() else "cpu") if setting == "auto" else setting


@cache
def _model(name: str, max_length: int, device: str) -> CrossEncoder:
    model = CrossEncoder(name, max_length=max_length, device=device)
    return model.half() if device == "cuda" else model  # fp16 is slower than fp32 on CPU


def rerank(query: str, hits: list[dict], cfg: dict) -> list[dict]:
    r = cfg["rerank"]
    if not hits:
        return []
    scores = _model(r["model"], r["max_length"], _device(r["device"])).predict(
        [(query, h["text"]) for h in hits], batch_size=r["batch_size"], show_progress_bar=False)
    order = sorted(range(len(hits)), key=lambda i: -scores[i])
    return [{**hits[i], "score": float(scores[i])} for i in order]


def release() -> None:
    """Free the reranker's VRAM so the generator LLM fits on the 6 GB GPU afterwards."""
    _model.cache_clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
