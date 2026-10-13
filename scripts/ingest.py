"""Ingest a split's papers into the local Qdrant index (collection named after the split).

    uv run python scripts/ingest.py --split dev_slice
"""

import argparse
import json

from halo.config import ROOT, load_config
from halo.ingest.index import ingest_papers, open_index


def split_papers(split: str) -> list[str]:
    return json.loads((ROOT / "splits" / f"{split}.json").read_text(encoding="utf-8"))["paper_ids"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev_slice")
    args = parser.parse_args()
    cfg = load_config()
    ingest_papers(open_index(cfg), args.split, split_papers(args.split), cfg)


if __name__ == "__main__":
    main()
