"""Ingest papers into a local Qdrant collection: PDF blocks -> section mapping -> chunks -> embeddings."""

import json
import urllib.request
import uuid

from qdrant_client import QdrantClient, models

from halo.config import ROOT
from halo.data import load_corpus_doc, pdf_dir
from halo.ingest.pdf import read_blocks
from halo.ingest.sections import chunk_blocks, map_blocks, section_title


def embed(texts: list[str], prefix: str, cfg: dict) -> list[list[float]]:
    """Embed with Ollama's /api/embed (one batched request)."""
    m = cfg["models"]
    body = json.dumps({"model": m["embedding"], "input": [prefix + t for t in texts]}).encode()
    req = urllib.request.Request(f"{m['ollama_url']}/api/embed", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=cfg["data"]["http_timeout_seconds"]) as r:
        return json.load(r)["embeddings"]


def open_index(cfg: dict) -> QdrantClient:
    return QdrantClient(path=str(ROOT / cfg["index"]["qdrant_path"]))


def point_id(paper_id: str, chunk_idx: int) -> str:
    """Deterministic ID: re-ingesting a paper overwrites its points instead of duplicating them."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"halo:{paper_id}:{chunk_idx}"))


def paper_chunks(paper_id: str, cfg: dict) -> tuple[list[dict], list[dict]]:
    """(chunks with full metadata, per-block mapping results) for one paper."""
    ing = cfg["ingest"]
    sections = load_corpus_doc(paper_id, cfg)["sections"]
    if not sections:
        raise ValueError(f"{paper_id}: corpus doc has no sections to map to")
    titles = {s["section_id"]: section_title(s["text"]) for s in sections}
    blocks = read_blocks(pdf_dir(cfg) / f"{paper_id}.pdf")
    mapping = map_blocks([b["text"] for b in blocks], sections, ing["shingle_n"], ing["min_match"])
    mapped = [{**b, "section_id": m["section_id"]} for b, m in zip(blocks, mapping)]
    chunks = [
        {"paper_id": paper_id, "chunk_idx": i, "section_title": titles[c["section_id"]], **c}
        for i, c in enumerate(chunk_blocks(mapped, ing["chunk_words"], ing["overlap_words"]))
    ]
    return chunks, mapping


def _paper_filter(paper_id: str) -> models.Filter:
    return models.Filter(must=[models.FieldCondition(key="paper_id", match=models.MatchValue(value=paper_id))])


def ingest_papers(client: QdrantClient, collection: str, paper_ids: list[str], cfg: dict) -> list[dict]:
    """Re-index each paper (delete its old points, upsert new ones). Returns block mappings for stats."""
    idx = cfg["index"]
    all_mappings = []
    for n, pid in enumerate(paper_ids, 1):
        chunks, mapping = paper_chunks(pid, cfg)
        all_mappings.extend({"paper_id": pid, **m} for m in mapping)
        # ponytail: re-embeds every chunk on each run (~minutes for dev_slice); add a content-hash
        # cache if full-corpus re-ingestion gets slow.
        vectors = []
        for i in range(0, len(chunks), idx["embed_batch"]):
            vectors += embed([c["text"] for c in chunks[i:i + idx["embed_batch"]]], idx["doc_prefix"], cfg)
        if not client.collection_exists(collection):
            client.create_collection(collection, vectors_config=models.VectorParams(
                size=len(vectors[0]), distance=models.Distance.COSINE))
        # Delete first so a paper that now yields fewer chunks leaves no stale points behind.
        client.delete(collection, points_selector=models.FilterSelector(filter=_paper_filter(pid)))
        client.upsert(collection, points=[
            models.PointStruct(id=point_id(pid, c["chunk_idx"]), vector=v, payload=c)
            for c, v in zip(chunks, vectors)
        ])
        print(f"[{n}/{len(paper_ids)}] {pid}: {len(chunks)} chunks", flush=True)
    return all_mappings


def search(client: QdrantClient, collection: str, query: str, k: int, cfg: dict) -> list[dict]:
    vec = embed([query], cfg["index"]["query_prefix"], cfg)[0]
    hits = client.query_points(collection, query=vec, limit=k, with_payload=True).points
    return [{"score": h.score, **h.payload} for h in hits]


def all_payloads(client: QdrantClient, collection: str) -> list[dict]:
    out, offset = [], None
    while True:
        points, offset = client.scroll(collection, limit=1000, offset=offset, with_payload=True)
        out += [{"id": p.id, **p.payload} for p in points]
        if offset is None:
            return out
