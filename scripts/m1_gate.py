"""M1 gate: ingest dev_slice twice and check metadata, qrels coverage, idempotency; spot-check search.

    uv run python scripts/m1_gate.py

Writes results/m1_gate.txt. Exits non-zero if a hard check fails.
"""

import json
import statistics
import sys
from collections import Counter

from halo.config import ROOT, load_config
from halo.data import load_corpus_doc, load_hf
from halo.ingest.index import all_payloads, ingest_papers, open_index, search
from scripts.ingest import split_papers

SPLIT = "dev_slice"
SPOT_CHECKS = 5
SPOT_K = 3
REQUIRED = ("paper_id", "section_id", "page")

lines: list[str] = []
failures: list[str] = []


def out(s: str = "") -> None:
    print(s)
    lines.append(s)


def check(label: str, ok: bool, detail: str) -> None:
    out(f"  [{'OK' if ok else 'FAIL'}] {label}: {detail}")
    if not ok:
        failures.append(label)


def snapshot(client) -> tuple[int, set, Counter]:
    payloads = all_payloads(client, SPLIT)
    keys = Counter((p["paper_id"], p["chunk_idx"]) for p in payloads)
    return len(payloads), {(p["id"], p["text"]) for p in payloads}, keys


def mapping_stats(mappings: list[dict]) -> None:
    scores = sorted(m["score"] for m in mappings)
    inherited = sum(m["inherited"] for m in mappings)
    q = statistics.quantiles(scores, n=10)
    out(f"  blocks: {len(mappings)}, inherited (score < min_match): {inherited} ({inherited / len(mappings):.1%})")
    out("  score deciles: " + " ".join(f"{x:.2f}" for x in q))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # chunk text has math symbols; Windows console is cp1252
    cfg = load_config()
    client = open_index(cfg)
    papers = split_papers(SPLIT)

    out(f"# M1 gate — {SPLIT} ({len(papers)} papers)")
    out(f"config: ingest={cfg['ingest']} embedding={cfg['models']['embedding']}")
    out("\n## Ingestion run 1")
    mappings = ingest_papers(client, SPLIT, papers, cfg)
    mapping_stats(mappings)
    n1, content1, _ = snapshot(client)

    out("\n## 1. Metadata coverage")
    payloads = all_payloads(client, SPLIT)
    missing = [p["id"] for p in payloads if any(p.get(f) is None for f in REQUIRED)]
    check("chunks with paper_id, section_id, page", not missing, f"{len(payloads) - len(missing)}/{len(payloads)}")
    out(f"  chunks per paper: {statistics.median(Counter(p['paper_id'] for p in payloads).values())} median")

    out("\n## 2. qrels sections covered by >=1 chunk (dev_sample)")
    qrels = load_hf("qrels.json", cfg)
    qids = json.loads((ROOT / "splits" / "dev_sample.json").read_text(encoding="utf-8"))["query_ids"]
    chunk_sections = {(p["paper_id"], p["section_id"]) for p in payloads}
    gold = {(qrels[q]["doc_id"], qrels[q]["section_id"]) for q in qids}
    unmapped = sorted(gold - chunk_sections)
    check("qrels sections with a chunk", not unmapped, f"{len(gold) - len(unmapped)}/{len(gold)}")
    for doc_id, sid in unmapped:
        text = load_corpus_doc(doc_id, cfg)["sections"][sid]["text"]
        n_q = sum(1 for q in qids if (qrels[q]["doc_id"], qrels[q]["section_id"]) == (doc_id, sid))
        out(f"    unmapped {doc_id} s{sid} ({n_q} questions, {len(text)} chars): {text[:100]!r}")

    out("\n## 3. Idempotency (ingestion run 2)")
    ingest_papers(client, SPLIT, papers, cfg)
    n2, content2, keys2 = snapshot(client)
    check("same chunk count", n1 == n2, f"{n1} -> {n2}")
    check("no duplicate (paper_id, chunk_idx)", max(keys2.values()) == 1, f"max copies {max(keys2.values())}")
    check("identical ids and texts", content1 == content2, "byte-equal" if content1 == content2 else "differ")

    out(f"\n## 4. Spot checks (first {SPOT_CHECKS} text-modality dev_sample questions by id, top {SPOT_K})")
    queries = load_hf("queries.json", cfg)
    picks = [q for q in qids if queries[q]["source"] == "text"][:SPOT_CHECKS]
    for q in picks:
        g = qrels[q]
        out(f"\nQ: {queries[q]['query']}\n   gold: {g['doc_id']} s{g['section_id']}")
        for rank, h in enumerate(search(client, SPLIT, queries[q]["query"], SPOT_K, cfg), 1):
            hit = "GOLD" if (h["paper_id"], h["section_id"]) == (g["doc_id"], g["section_id"]) else "    "
            out(f"   {rank}. {hit} {h['score']:.3f} {h['paper_id']} s{h['section_id']} p{h['page']} "
                f"[{h['section_title'][:40]}] {h['text'][:160]!r}")

    (ROOT / "results" / "m1_gate.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
