"""M9 contextual enrichment: an LLM writes 1-2 lines situating each chunk in its paper (DECISIONS.md D42).

The context goes into the chunk payload as "context"; sections.index_text() prepends it for embedding, BM25 and
reranking. Generations are cached in a JSONL file keyed by content, so re-ingesting costs no LLM calls.
"""

import hashlib
import json
from pathlib import Path

from halo.config import ROOT
from halo.llm import chat


def cache_key(paper_id: str, text: str, e: dict) -> str:
    """Changes when the model, the prompt version, the paper or the chunk text change, never otherwise."""
    return hashlib.sha256(json.dumps([e["model"], e["prompt_version"], paper_id, text]).encode()).hexdigest()


COST = ("prompt_tokens", "output_tokens", "ms")


class EnrichCache:
    """Append-only JSONL: {"key", "context", prompt_tokens, output_tokens, ms} per line. A run killed mid-write
    leaves at most one truncated last line, which is skipped (that chunk is regenerated)."""

    def __init__(self, path: Path):
        self.path = path
        self._d = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._d[rec["key"]] = rec

    def get(self, key: str) -> dict | None:
        return self._d.get(key)

    def put(self, key: str, rec: dict) -> None:
        rec = {"key": key, **rec}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        self._d[key] = rec


def open_cache(cfg: dict) -> EnrichCache:
    return EnrichCache(ROOT / cfg["enrich"]["cache_path"])


def situate(chunk: dict, doc: dict, cfg: dict) -> dict:
    """One LLM call. Returns chat()'s dict (content, token counts, ms)."""
    e = cfg["enrich"]
    prompt = e["user_prompt"].format(title=" ".join(doc["title"].split()), abstract=" ".join(doc["abstract"].split()),
                                     section=chunk["section_title"] or "(untitled)", passage=chunk["text"])
    # [enrich] num_gpu overrides [llm]: the generator's value leaves room for the reranker, unused at ingest.
    return chat(e["system_prompt"], prompt, e["model"], e["max_tokens"], cfg | {"llm": cfg["llm"] | {"num_gpu": e["num_gpu"]}})


def enrich(chunks: list[dict], doc: dict, cfg: dict, cache: EnrichCache, stats: dict) -> list[dict]:
    """Copies of chunks with "context" added. Updates stats in place: chunks, calls (cache misses this run), and the
    LLM cost of every chunk's context (tokens, ms), whether generated now or by an earlier, interrupted run."""
    out = []
    for c in chunks:
        key = cache_key(c["paper_id"], c["text"], cfg["enrich"])
        rec = cache.get(key)
        if rec is None:
            resp = situate(c, doc, cfg)
            rec = {"context": " ".join(resp["content"].split())} | {k: resp[k] for k in COST}
            cache.put(key, rec)
            stats["calls"] = stats.get("calls", 0) + 1
        stats["chunks"] = stats.get("chunks", 0) + 1
        for k in COST:
            stats[k] = stats.get(k, 0) + rec.get(k, 0)
        out.append({**c, "context": rec["context"]})
    return out
