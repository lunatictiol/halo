"""Create the evaluation splits (design: CLAUDE.md > Dataset, rationale: DECISIONS.md).

    uv run python scripts/make_splits.py           # write splits/*.json
    uv run python scripts/make_splits.py --check   # regenerate in memory, fail if files differ

One fixed seed from config. It is never re-rolled to get a nicer distribution.
"""

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict

from halo.config import ROOT, load_config
from halo.data import hf_dir, load_corpus_doc, load_hf, sha256_file

SPLITS_DIR = ROOT / "splits"


def build_splits(qrels: dict, pdf_urls: dict, categories: dict, seed: int,
                 held_out_papers: int, dev_sample_min_questions: int, dev_distractors: int) -> dict:
    """Pure function: same inputs + seed -> same splits. Returns {split_name: payload}."""
    questions_by_doc = defaultdict(list)
    for qid, rel in qrels.items():
        questions_by_doc[rel["doc_id"]].append(qid)
    sources = sorted(questions_by_doc)
    distractors = sorted(set(pdf_urls) - set(sources))

    rng = random.Random(seed)
    order = sources[:]
    rng.shuffle(order)
    held = order[:held_out_papers]

    dev_src, n_dev_q = [], 0
    for doc in order[held_out_papers:]:
        if n_dev_q >= dev_sample_min_questions:
            break
        dev_src.append(doc)
        n_dev_q += len(questions_by_doc[doc])

    # Distractors from the same primary arXiv categories as the dev sources, so dev retrieval
    # is as hard as full-corpus retrieval. Topped up at random only if too few match.
    dev_cats = {categories[d][0] for d in dev_src}
    matched = [d for d in distractors if categories[d][0] in dev_cats]
    if len(matched) >= dev_distractors:
        chosen = rng.sample(matched, dev_distractors)
    else:
        rest = [d for d in distractors if d not in set(matched)]
        chosen = matched + rng.sample(rest, dev_distractors - len(matched))
    n_matched = sum(categories[d][0] in dev_cats for d in chosen)

    held_q = sorted(q for d in held for q in questions_by_doc[d])
    held_q_set = set(held_q)
    return {
        "held_out": {"paper_ids": sorted(held), "query_ids": []},
        "abstention_set": {"paper_ids": sorted(held), "query_ids": held_q},
        "dev_slice": {
            "paper_ids": sorted(dev_src + chosen),
            "query_ids": [],
            "source_paper_ids": sorted(dev_src),
            "distractor_paper_ids": sorted(chosen),
            "distractors_category_matched": n_matched,
        },
        "dev_sample": {"paper_ids": sorted(dev_src),
                       "query_ids": sorted(q for d in dev_src for q in questions_by_doc[d])},
        "full": {"paper_ids": sorted(set(pdf_urls) - set(held)),
                 "query_ids": sorted(q for q in qrels if q not in held_q_set)},
    }


def check_invariants(splits: dict) -> None:
    held = set(splits["held_out"]["paper_ids"])
    abst = set(splits["abstention_set"]["query_ids"])
    assert held.isdisjoint(splits["dev_slice"]["paper_ids"]), "held-out paper in dev_slice"
    assert held.isdisjoint(splits["full"]["paper_ids"]), "held-out paper in full index"
    assert abst.isdisjoint(splits["dev_sample"]["query_ids"]), "abstention question in dev_sample"
    assert abst.isdisjoint(splits["full"]["query_ids"]), "abstention question in full"


def render(name: str, payload: dict, seed: int, inputs_sha256: dict) -> str:
    doc = {"name": name, "seed": seed, "inputs_sha256": inputs_sha256, **payload}
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def print_distribution(queries: dict, splits: dict) -> None:
    sets = {"full (answerable)": splits["full"]["query_ids"],
            "dev_sample": splits["dev_sample"]["query_ids"],
            "abstention_set": splits["abstention_set"]["query_ids"]}
    for field in ("type", "source"):
        values = sorted({queries[q][field] for q in queries})
        print(f"\nBy {field}:")
        print(f"  {'':<18}" + "".join(f"{v:>20}" for v in values) + f"{'n':>7}")
        for label, qids in sets.items():
            c = Counter(queries[q][field] for q in qids)
            cells = "".join(f"{100 * c[v] / len(qids):>19.1f}%" for v in values)
            print(f"  {label:<18}{cells}{len(qids):>7}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify splits/ is reproducible")
    args = parser.parse_args()

    cfg = load_config()
    s = cfg["splits"]
    qrels, queries, pdf_urls = load_hf("qrels.json"), load_hf("queries.json"), load_hf("pdf_urls.json")
    categories = {d: load_corpus_doc(d)["categories"] for d in sorted(pdf_urls)}
    inputs_sha256 = {
        name: sha256_file(hf_dir() / name) for name in ("qrels.json", "queries.json", "pdf_urls.json")
    }
    inputs_sha256["corpus_categories"] = hashlib.sha256(
        json.dumps(categories, sort_keys=True).encode()).hexdigest()

    splits = build_splits(qrels, pdf_urls, categories, s["seed"], s["held_out_papers"],
                          s["dev_sample_min_questions"], s["dev_distractors"])
    check_invariants(splits)
    rendered = {name: render(name, p, s["seed"], inputs_sha256) for name, p in splits.items()}

    if args.check:
        bad = [n for n, text in rendered.items()
               if not (SPLITS_DIR / f"{n}.json").exists()
               or (SPLITS_DIR / f"{n}.json").read_bytes() != text.encode()]
        for n in rendered:
            if n not in bad:
                print(f"OK   {n}.json  sha256={hashlib.sha256(rendered[n].encode()).hexdigest()[:16]}")
        if bad:
            sys.exit(f"MISMATCH: {bad}")
        print("All split files reproduce byte-identically.")
    else:
        SPLITS_DIR.mkdir(exist_ok=True)
        for n, text in rendered.items():
            (SPLITS_DIR / f"{n}.json").write_bytes(text.encode())
        print(f"Wrote {len(rendered)} split files to {SPLITS_DIR}")

    ds = splits["dev_slice"]
    print(f"\nheld_out papers: {len(splits['held_out']['paper_ids'])}, "
          f"abstention questions: {len(splits['abstention_set']['query_ids'])}")
    print(f"dev_slice: {len(ds['paper_ids'])} papers = {len(ds['source_paper_ids'])} source + "
          f"{len(ds['distractor_paper_ids'])} distractors "
          f"({ds['distractors_category_matched']} category-matched)")
    print(f"dev_sample questions: {len(splits['dev_sample']['query_ids'])}, "
          f"full questions: {len(splits['full']['query_ids'])}, "
          f"full index papers: {len(splits['full']['paper_ids'])}")
    print_distribution(queries, splits)


if __name__ == "__main__":
    main()
