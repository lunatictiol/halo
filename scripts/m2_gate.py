"""M2 gate: retrieval-metric determinism, baseline results + summary table, judge verdict sample.

    uv run python scripts/m2_gate.py

Run after `eval.runners.run` has finished on dev_sample and abstention_set. Writes results/m2_gate.txt and
results/m2_judge_sample.md (10 verdicts for manual review). Exits non-zero if a hard check fails.
"""

import hashlib
import json
import random
import sys

from eval.metrics.retrieval import query_metrics
from eval.metrics.slices import summarize
from eval.report.summary import build
from eval.results import RESULTS_DIR
from eval.runners.run import load_queries, retrieve_all
from halo.config import load_config
from halo.data import data_dir
from halo.generate.baseline import format_context

SPLIT, RUN = "dev_sample", "m2_baseline"
SAMPLE_SEED = 20261015
# 5 faithfulness + 5 correctness verdicts; up to 2 of each are drawn from negative verdicts so the sample
# exercises both labels (positives dominate, so a uniform sample could contain no negative at all).
PER_KIND, MAX_NEGATIVES = 5, 2

lines: list[str] = []
failures: list[str] = []


def out(s: str = "") -> None:
    print(s)
    lines.append(s)


def check(label: str, ok: bool, detail: str) -> None:
    out(f"  [{'OK' if ok else 'FAIL'}] {label}: {detail}")
    if not ok:
        failures.append(label)


def retrieval_summary(queries: list[dict], retrieved: dict, cfg: dict) -> tuple[dict, list]:
    r = cfg["retrieve"]
    recs = [q | query_metrics([(h["paper_id"], h["section_id"]) for h in retrieved[q["query_id"]]["hits"]],
                              tuple(q["gold"]), tuple(r["recall_ks"]), r["k_eval"], r["k_eval"]) for q in queries]
    metrics = [f"recall@{k}" for k in r["recall_ks"]] + ["mrr", f"ndcg@{r['k_eval']}", f"paper_hit@{r['k_eval']}"]
    rankings = [[(h["paper_id"], h["chunk_idx"]) for h in retrieved[q["query_id"]]["hits"]] for q in queries]
    return summarize(recs, metrics), rankings


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def determinism(cfg: dict) -> None:
    out(f"\n## 1. Retrieval metrics are deterministic ({SPLIT}, two fresh runs)")
    queries = load_queries(SPLIT, cfg)
    (m1, rank1), (m2, rank2) = (retrieval_summary(queries, retrieve_all(queries, cfg), cfg) for _ in range(2))
    check("identical metrics", m1 == m2, f"sha {_sha(m1)} vs {_sha(m2)}")
    check("identical rankings", rank1 == rank2, f"{sum(a == b for a, b in zip(rank1, rank2))}/{len(rank1)} queries")
    stored = json.loads((data_dir(cfg) / "runs" / f"{RUN}_{SPLIT}" / "retrieve.json").read_text(encoding="utf-8"))
    m3, _ = retrieval_summary(queries, stored, cfg)
    check("matches the baseline run's retrieval", m3 == m1, f"sha {_sha(m3)}")
    o = m1["overall"]
    out("  " + ", ".join(f"{k}={v['mean']}" for k, v in o.items()))


def _verdicts(per_query: list[dict], kind: str) -> list[dict]:
    return [{"kind": kind, **r} for r in per_query if r[kind] and r[kind]["verdict"] is not None]


def judge_sample(res: dict, cfg: dict) -> list[dict]:
    rng = random.Random(SAMPLE_SEED)
    sample = []
    for kind, negative in (("faithfulness", "unsupported"), ("correctness", "incorrect")):
        pool = _verdicts(res["per_query"], kind)
        neg = [r for r in pool if r[kind]["verdict"] == negative]
        picked = rng.sample(neg, min(MAX_NEGATIVES, len(neg)))
        rest = [r for r in pool if r not in picked]
        sample += picked + rng.sample(rest, PER_KIND - len(picked))
    return sample


def sample_markdown(sample: list[dict], cfg: dict) -> str:
    retrieved = json.loads((data_dir(cfg) / "runs" / f"{RUN}_{SPLIT}" / "retrieve.json").read_text(encoding="utf-8"))
    k = cfg["retrieve"]["k_context"]
    md = ["# M2 judge sample: 10 verdicts for manual review", "",
          f"Judge `{cfg['judge']['model']}` ({cfg['judge']['prompt_version']}). Sample seed {SAMPLE_SEED}; up to "
          f"{MAX_NEGATIVES} negatives per kind are oversampled. Mark each **agree / disagree**.", ""]
    for i, r in enumerate(sample, 1):
        v = r[r["kind"]]
        md += [f"## {i}. {r['kind']}: **{v['verdict']}**  (`{r['query_id']}`, {r['type']}, {r['source']})", "",
               f"**Question:** {r['query']}", "", f"**Answer:** {r['answer']}", ""]
        if r["kind"] == "correctness":
            md += [f"**Reference:** {r['reference']}", ""]
        else:
            md += ["<details><summary>Retrieved context given to the generator and judge</summary>", "", "```",
                   format_context(retrieved[r["query_id"]]["hits"][:k]), "```", "</details>", ""]
        md += [f"**Judge reason:** {v['reason']}", "", "**Your call:** agree / disagree", ""]
    return "\n".join(md)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_config()
    out(f"# M2 gate — {SPLIT}")
    out("\n## 0. Metric unit tests: run `uv run pytest` (reported separately)")
    determinism(cfg)

    out("\n## 2. Baseline results and summary table")
    res = json.loads((RESULTS_DIR / f"{RUN}_{SPLIT}.json").read_text(encoding="utf-8"))
    check("results file covers the split", res["n_queries"] == len(load_queries(SPLIT, cfg)), f"{res['n_queries']} queries")
    check("judge errors", res["judge_errors"] == 0, f"{res['judge_errors']}/{res['judge_calls']} (allowed 0)")
    out(build(RUN))

    out("\n## 3. Judge sample for manual review")
    sample = judge_sample(res, cfg)
    (RESULTS_DIR / "m2_judge_sample.md").write_text(sample_markdown(sample, cfg), encoding="utf-8")
    out(f"  wrote results/m2_judge_sample.md ({len(sample)} verdicts)")

    out(f"\nGATE {'FAILED: ' + ', '.join(failures) if failures else 'PASSED (pending manual judge review)'}")
    (RESULTS_DIR / "m2_gate.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
