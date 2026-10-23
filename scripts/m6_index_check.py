"""M6: check the full-corpus index (built by `scripts/ingest.py --split full`) without re-ingesting.

    uv run python scripts/m6_index_check.py

Writes results/m6_index.txt. Exits non-zero if a check fails. Idempotency of ingestion was shown in M1
(results/m1_gate.txt); here the same property is checked as "no duplicate (paper_id, chunk_idx)".
"""

import json
import statistics
import sys
from collections import Counter

from halo.config import ROOT, load_config
from halo.data import load_corpus_doc, load_hf
from halo.ingest.index import NO_SECTION, all_payloads, open_index
from scripts.ingest import split_papers
from scripts.m1_gate import REQUIRED, check, failures, lines, out

COLLECTION = "full"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_config()
    client = open_index(cfg)
    try:
        payloads = all_payloads(client, COLLECTION)
    finally:
        client.close()
    papers, held_out = set(split_papers(COLLECTION)), set(split_papers("held_out"))
    indexed = Counter(p["paper_id"] for p in payloads)

    out(f"# M6 full-corpus index ({len(payloads)} chunks)")
    check("every full-split paper indexed", set(indexed) == papers, f"{len(indexed)}/{len(papers)} papers")
    check("no held_out paper indexed", not set(indexed) & held_out, f"{len(set(indexed) & held_out)} found")
    missing = [p["id"] for p in payloads if any(p.get(f) is None for f in REQUIRED)]
    check("chunks with paper_id, section_id, page", not missing, f"{len(payloads) - len(missing)}/{len(payloads)}")
    keys = Counter((p["paper_id"], p["chunk_idx"]) for p in payloads)
    check("no duplicate (paper_id, chunk_idx)", max(keys.values()) == 1, f"max copies {max(keys.values())}")
    out(f"  chunks per paper: median {statistics.median(indexed.values())}, min {min(indexed.values())}, "
        f"max {max(indexed.values())}")

    no_section = sorted({p["paper_id"] for p in payloads if p["section_id"] == NO_SECTION})
    out(f"\n## Papers without Vectara sections (indexed under section {NO_SECTION}): {len(no_section)}")
    for pid in no_section:
        out(f"  {pid}: {indexed[pid]} chunks, {load_corpus_doc(pid, cfg)['title']!r}")

    out("\n## qrels sections covered by >=1 chunk (full split)")
    qrels = load_hf("qrels.json", cfg)
    qids = json.loads((ROOT / "splits" / "full.json").read_text(encoding="utf-8"))["query_ids"]
    chunk_sections = {(p["paper_id"], p["section_id"]) for p in payloads}
    gold = Counter((qrels[q]["doc_id"], qrels[q]["section_id"]) for q in qids)
    unmapped = sorted(set(gold) - chunk_sections)
    n_lost = sum(gold[g] for g in unmapped)
    # Listed, not a hard check: a gold section with no chunk is a known ingestion limit (M1, results/m1_mapping.txt).
    out(f"  sections: {len(gold) - len(unmapped)}/{len(gold)} mapped; questions whose gold section has no chunk: "
        f"{n_lost}/{len(qids)} ({n_lost / len(qids):.1%}), a hard retrieval ceiling")
    for doc_id, sid in unmapped:
        text = load_corpus_doc(doc_id, cfg)["sections"][sid]["text"]
        out(f"    unmapped {doc_id} s{sid} ({gold[doc_id, sid]} questions, {len(text)} chars): {text[:100]!r}")

    (ROOT / "results" / "m6_index.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
