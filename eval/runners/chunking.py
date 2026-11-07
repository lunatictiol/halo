"""M9 chunking benchmark: retrieval metrics per chunking strategy (one Qdrant collection each), no LLM.

    uv run python -m eval.runners.chunking                       # all strategies, dense + hybrid_rerank
    uv run python -m eval.runners.chunking --strategies fixed     # (re)run one; the table reads the rest from disk

Writes results/m9_retrieval_<strategy>_<method>_<split>.json and results/m9_chunking.md. Ingest time and enrichment
cost come from results/m9_ingest_<collection>.json (scripts/ingest.py).
"""

import argparse
import copy
import json

from eval.results import RESULTS_DIR
from eval.runners.ablation import COLUMNS, _cells, evaluate, paired_vs
from halo.config import load_config

# strategy -> collection built by scripts/ingest.py (DECISIONS.md D41-D42)
COLLECTIONS = {"section": "dev_slice", "fixed": "dev_slice_fixed", "ctx": "dev_slice_ctx"}
# dense isolates the embedding effect; hybrid_rerank is the shipped pipeline's retrieval.
METHODS = ("dense", "hybrid_rerank")
METRICS = [m for m, _ in COLUMNS if m != "paper_hit@10"]
HEADS = [h for m, h in COLUMNS if m != "paper_hit@10"]


def result_name(strategy: str, method: str, split: str) -> str:
    return f"m9_retrieval_{strategy}_{method}_{split}"


def _load(name: str) -> dict | None:
    p = RESULTS_DIR / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def ingest_cells(collection: str) -> str:
    ing = _load(f"m9_ingest_{collection}")
    if ing is None:
        return "– | – | –"
    e = ing["enrich"]
    cost = "none" if e is None else (f"{e.get('calls', 0)} calls, {e.get('prompt_tokens', 0):,} in / "
                                     f"{e.get('output_tokens', 0):,} out tokens, {e.get('ms', 0) / 3.6e6:.1f} h LLM")
    return f"{ing['n_chunks']:,} | {ing['wall_seconds'] / 60:.0f} min | {cost}"


def chart(results: dict, method: str, metric: str, label: str) -> list[str]:
    names = [s for s in COLLECTIONS if (s, method) in results]
    vals = [round(results[(s, method)]["metrics"]["overall"][metric]["mean"], 3) for s in names]
    lo = max(0.0, round(min(vals) - 0.05, 1))
    return ["```mermaid", "xychart-beta", f'    title "{label} by chunking strategy ({method}, dev_sample)"',
            "    x-axis [" + ", ".join(names) + "]", f'    y-axis "{label}" {lo} --> 1',
            "    bar [" + ", ".join(map(str, vals)) + "]", "```"]


def coverage_lines(results: dict, labels: dict[str, set]) -> list[str]:
    """Fixed-size chunks carry their majority section, so a short gold section may label no chunk at all and be
    unreachable by construction. Compare strategies on the questions every strategy can reach."""
    base = _per_query(results, "section", "hybrid_rerank")
    reachable = {q for q, rec in base.items() if all(tuple(rec["gold"]) in labs for labs in labels.values())}
    lines = ["", "## Reachable gold sections", "",
             "A question is reachable when at least one chunk carries its gold (paper, section) label. Fixed-size "
             "chunks take their majority section, so short sections can label no chunk.", "",
             "| Strategy | Questions with a reachable gold section |", "|---|---|"]
    lines += [f"| {s} | {sum(tuple(r['gold']) in labels[s] for r in base.values())} / {len(base)} |"
              for s in COLLECTIONS if s in labels]
    lines += ["", f"Metrics on the {len(reachable)} questions reachable by every strategy (R@5 / MRR):", "",
              "| Strategy | " + " | ".join(METHODS) + " |", "|---" * (len(METHODS) + 1) + "|"]
    for s in COLLECTIONS:
        cells = []
        for m in METHODS:
            pq = _per_query(results, s, m)
            cells.append(f"{sum(pq[q]['recall@5'] for q in reachable) / len(reachable):.3f} / "
                         f"{sum(pq[q]['mrr'] for q in reachable) / len(reachable):.3f}" if pq else "–")
        lines.append(f"| {s} | " + " | ".join(cells) + " |")
    return lines


def _per_query(results: dict, strategy: str, method: str) -> dict:
    res = results.get((strategy, method))
    return {p["query_id"]: p for p in res["per_query"]} if res else {}


def section_labels() -> dict[str, set]:
    """(paper_id, section_id) labels present in each strategy's collection."""
    from halo.ingest.index import all_payloads, open_index
    client = open_index(load_config())
    try:
        return {s: {(c["paper_id"], c["section_id"]) for c in all_payloads(client, coll)}
                for s, coll in COLLECTIONS.items() if client.collection_exists(coll)}
    finally:
        client.close()


def report(results: dict, split: str, labels: dict[str, set] | None = None) -> str:
    any_res = next(iter(results.values()))
    lines = [f"# M9 chunking benchmark on `{split}`", "",
             f"n = {any_res['n_queries']} queries, 100-paper dev_slice index per strategy. Commit "
             f"`{any_res['git']['commit']}`{' (dirty)' if any_res['git']['dirty'] else ''}. Source files: "
             + ", ".join(f"`results/{result_name(s, m, split)}.json`" for s, m in results) + ".", "",
             "## Retrieval", "",
             "| Strategy | Method | " + " | ".join(HEADS) + " | Gold rank vs section |", "|---" * (len(HEADS) + 3) + "|"]
    for method in METHODS:
        for s in COLLECTIONS:
            if (s, method) not in results:
                continue
            base = results.get(("section", method))
            vs = paired_vs(base, results[(s, method)]) if base and s != "section" else "–"
            lines.append(f"| {s} | {method} | {_cells(results[(s, method)]['metrics']['overall'], METRICS)} | {vs} |")
    lines += ["", "Gold rank vs section: queries whose first gold chunk moved up / down in the top-10, same method.", "",
              "## Ingest cost", "", "| Strategy | Collection | Chunks | Ingest wall time | Enrichment |", "|---|---|---|---|---|"]
    lines += [f"| {s} | `{c}` | {ingest_cells(c)} |" for s, c in COLLECTIONS.items()]
    for slice_name, label in (("by_modality", "modality"), ("by_type", "question type")):
        groups = any_res["metrics"][slice_name]
        lines += ["", f"## By {label}, hybrid_rerank (R@5 / MRR)", "",
                  "| Strategy | " + " | ".join(f"{g} (n={groups[g]['mrr']['n']})" for g in groups) + " |",
                  "|---" * (len(groups) + 1) + "|"]
        for s in COLLECTIONS:
            if (res := results.get((s, "hybrid_rerank"))) is None:
                continue
            blk = res["metrics"][slice_name]
            lines.append(f"| {s} | " + " | ".join(
                f"{blk[g]['recall@5']['mean']:.3f} / {blk[g]['mrr']['mean']:.3f}" for g in groups) + " |")
    if labels:
        lines += coverage_lines(results, labels)
    lines += ["", "## Charts", ""] + chart(results, "hybrid_rerank", "recall@5", "R@5") + [""] \
        + chart(results, "hybrid_rerank", "mrr", "MRR")
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="dev_sample")
    p.add_argument("--strategies", default=",".join(COLLECTIONS))
    p.add_argument("--methods", default=",".join(METHODS))
    p.add_argument("--report-only", action="store_true", help="rebuild m9_chunking.md from saved results, no retrieval")
    a = p.parse_args()
    strategies, methods = a.strategies.split(","), a.methods.split(",")
    if bad := (set(strategies) - set(COLLECTIONS)) | (set(methods) - set(METHODS)):
        p.error(f"unknown {sorted(bad)}; strategies {list(COLLECTIONS)}, methods {list(METHODS)}")
    base_cfg = load_config()
    for s in [] if a.report_only else strategies:
        cfg = copy.deepcopy(base_cfg)
        cfg["retrieve"]["collection"] = COLLECTIONS[s]
        for m in methods:
            evaluate(m, a.split, cfg, name=result_name(s, m, a.split))
    results = {(s, m): r for s in COLLECTIONS for m in METHODS if (r := _load(result_name(s, m, a.split)))}
    md = report(results, a.split, section_labels())
    out = RESULTS_DIR / "m9_chunking.md"
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
