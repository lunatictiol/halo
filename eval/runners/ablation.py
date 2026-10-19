"""M3 retrieval ablation: every retrieval method on one split, retrieval metrics and latency only (no LLM).

    uv run python -m eval.runners.ablation                      # all methods on dev_sample
    uv run python -m eval.runners.ablation --methods dense,bm25

Writes results/m3_retrieval_<method>_<split>.json per method and results/m3_ablation.md.
"""

import argparse
import copy
import json
import statistics

from eval.metrics.retrieval import gold_rank, query_metrics, recall_at_k
from eval.metrics.slices import summarize
from eval.results import RESULTS_DIR, write_results
from eval.runners.run import load_queries, retrieve_all
from halo.config import load_config
from halo.retrieve import METHODS

COLUMNS = [("recall@5", "R@5"), ("recall@10", "R@10"), ("mrr", "MRR"), ("ndcg@10", "nDCG@10"),
           ("paper_hit@10", "Paper@10")]
STAGES = ("dense", "bm25", "fuse", "rerank")


def _pctl(values: list[float], q: int) -> float:
    return round(statistics.quantiles(values, n=100, method="inclusive")[q - 1], 1)


def latency(retrieved: dict) -> dict:
    """Median and p95 per stage and in total (ms per query, models already warm)."""
    recs = list(retrieved.values())
    stages = {"total": [r["retrieve_ms"] for r in recs]}
    for stage in recs[0]["stage_ms"]:
        stages[stage] = [r["stage_ms"][stage] for r in recs]
    return {s: {"median": round(statistics.median(v), 1), "p95": _pctl(v, 95)} for s, v in stages.items()}


def evaluate(method: str, split: str, cfg: dict) -> dict:
    cfg = copy.deepcopy(cfg)
    cfg["retrieve"]["method"] = method
    r = cfg["retrieve"]
    ks, kc = tuple(r["recall_ks"]), r["k_candidates"]
    queries = load_queries(split, cfg)
    print(f"{method}: retrieving {len(queries)} queries", flush=True)
    retrieved = retrieve_all(queries, cfg)
    recs = []
    for q in queries:
        ret, gold = retrieved[q["query_id"]], tuple(q["gold"])
        ranked = [(h["paper_id"], h["section_id"]) for h in ret["hits"]]
        recs.append({k: q[k] for k in ("query_id", "type", "source", "gold")}
                    | query_metrics(ranked, gold, ks, r["k_eval"], r["k_eval"])
                    | {f"recall@{kc}": recall_at_k(gold_rank([tuple(c) for c in ret["candidates"]], gold), kc),
                       "retrieved": ranked, "stage_ms": ret["stage_ms"]})
    names = [m for m, _ in COLUMNS] + [f"recall@{kc}"]
    payload = {"split": split, "kind": "retrieval_only", "method": method, "n_queries": len(recs),
               "metrics": summarize(recs, names), "latency_ms": latency(retrieved), "per_query": recs}
    path = write_results(f"m3_retrieval_{method}_{split}", payload, cfg)
    print(f"{method}: wrote {path}", flush=True)
    return json.loads(path.read_text(encoding="utf-8"))


def _cells(block: dict, names: list[str]) -> str:
    return " | ".join(f"{block[m]['mean']:.3f}" for m in names)


def paired_vs(base: dict, other: dict) -> str:
    """Per-query gold-rank comparison in the top-10: moved up / down / unchanged (not retrieved = worst)."""
    def ranks(res):
        return {p["query_id"]: p["gold_rank"] or float("inf") for p in res["per_query"]}
    b, o = ranks(base), ranks(other)
    up = sum(o[q] < b[q] for q in b)
    down = sum(o[q] > b[q] for q in b)
    return f"{up} better / {down} worse / {len(b) - up - down} same"


def report(results: dict[str, dict], split: str) -> str:
    first = next(iter(results.values()))
    c = first["config"]
    kc = c["retrieve"]["k_candidates"]
    names = [m for m, _ in COLUMNS] + [f"recall@{kc}"]
    heads = [h for _, h in COLUMNS] + [f"R@{kc} (ceiling)"]
    base = results.get("dense")
    lines = [f"# M3 retrieval ablation on `{split}`", "",
             f"n = {first['n_queries']} queries. Commit `{first['git']['commit']}`"
             f"{' (dirty)' if first['git']['dirty'] else ''}. Reranker `{c['rerank']['model']}`, "
             f"RRF k = {c['retrieve']['rrf_k']}, {kc} candidates per retriever. Source files: "
             + ", ".join(f"`results/m3_retrieval_{m}_{split}.json`" for m in results) + ".", "",
             "## Overall", "",
             "| Method | " + " | ".join(heads) + " | Latency median (ms) | Latency p95 (ms) | Gold rank vs dense |",
             "|---" * (len(heads) + 4) + "|"]
    for m, res in results.items():
        lat = res["latency_ms"]["total"]
        vs = paired_vs(base, res) if base and m != "dense" else "–"
        lines.append(f"| {m} | {_cells(res['metrics']['overall'], names)} | {lat['median']} | {lat['p95']} | {vs} |")
    lines += ["", f"R@{kc}: gold section anywhere in the candidate list, the most a reranker over that list could "
              "reach. Gold rank vs dense: queries whose first gold chunk moved up / down in the top-10.", "",
              "## Latency by stage (median / p95 ms per query)", "",
              "| Method | " + " | ".join(STAGES) + " |", "|---" * (len(STAGES) + 1) + "|"]
    for m, res in results.items():
        lat = res["latency_ms"]
        lines.append(f"| {m} | " + " | ".join(
            f"{lat[s]['median']} / {lat[s]['p95']}" if s in lat else "–" for s in STAGES) + " |")
    for slice_name, label in (("by_type", "question type"), ("by_modality", "modality")):
        groups = first["metrics"][slice_name]
        lines += ["", f"## By {label} (R@5 / MRR)", "",
                  "| Method | " + " | ".join(f"{g} (n={groups[g]['mrr']['n']})" for g in groups) + " |",
                  "|---" * (len(groups) + 1) + "|"]
        for m, res in results.items():
            blk = res["metrics"][slice_name]
            lines.append(f"| {m} | " + " | ".join(
                f"{blk[g]['recall@5']['mean']:.3f} / {blk[g]['mrr']['mean']:.3f}" for g in groups) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="dev_sample")
    p.add_argument("--methods", default=",".join(METHODS))
    a = p.parse_args()
    methods = a.methods.split(",")
    if unknown := set(methods) - set(METHODS):
        p.error(f"unknown methods {sorted(unknown)}; choose from {METHODS}")
    cfg = load_config()
    fresh = {m: evaluate(m, a.split, cfg) for m in methods}
    # The table covers every method with a results file, so one method can be (re)run on its own.
    results = {m: fresh.get(m) or json.loads(p.read_text(encoding="utf-8")) for m in METHODS
               if m in fresh or (p := RESULTS_DIR / f"m3_retrieval_{m}_{a.split}.json").exists()}
    md = report(results, a.split)
    out = RESULTS_DIR / "m3_ablation.md"
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
