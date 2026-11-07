"""Ingest a split's papers into the local Qdrant index.

    uv run python scripts/ingest.py --split dev_slice                                     # M1 section-aware chunks
    uv run python scripts/ingest.py --split dev_slice --strategy fixed --collection dev_slice_fixed   # M9

The collection defaults to the split name. M9 runs also write results/m9_ingest_<collection>.json
(wall time, chunk count, enrichment LLM calls and tokens).
"""

import argparse
import json
import time

from eval.results import write_results
from halo.config import ROOT, load_config
from halo.ingest.index import STRATEGIES, ingest_papers, open_index


def split_papers(split: str) -> list[str]:
    return json.loads((ROOT / "splits" / f"{split}.json").read_text(encoding="utf-8"))["paper_ids"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev_slice")
    parser.add_argument("--strategy", default="section", choices=STRATEGIES)
    parser.add_argument("--collection", help="defaults to the split name")
    args = parser.parse_args()
    cfg = load_config()
    collection = args.collection or args.split
    papers = split_papers(args.split)
    client = open_index(cfg)
    stats: dict = {}
    start = time.perf_counter()
    ingest_papers(client, collection, papers, cfg, args.strategy, stats)
    wall_s = round(time.perf_counter() - start, 1)
    if args.strategy != "section" or args.collection:
        path = write_results(f"m9_ingest_{collection}", {
            "kind": "ingest", "split": args.split, "strategy": args.strategy, "collection": collection,
            "n_papers": len(papers), "n_chunks": client.count(collection).count, "wall_seconds": wall_s,
            "enrich": stats if args.strategy == "ctx" else None}, cfg)
        print(f"wrote {path}")
    client.close()


if __name__ == "__main__":
    main()
