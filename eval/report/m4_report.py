"""M4 report: corrective loop vs M3 (same retrieval, generator, prompts and judge), loop statistics, and the
README examples (rescued first retrievals, correct abstentions).

    uv run python -m eval.report.m4_report        # -> results/m4_report.md
"""

import json
import sys

from eval.report.summary import ABSTENTION_SPLIT, ANSWERABLE_SPLIT
from eval.results import RESULTS_DIR

BASE, LOOP = "m3_hybrid_rerank", "m4_graph"
N_EXAMPLES = 5
ROWS = [("correct", "Correct"), ("correct_if_answered", "Correct|ans"), ("faithful", "Faithful"),
        ("abstained", "False-abstention"), ("mrr", "MRR (context used)"), ("recall@5", "R@5 (context used)")]


def _load(name: str, split: str) -> dict:
    return json.loads((RESULTS_DIR / f"{name}_{split}.json").read_text(encoding="utf-8"))


def _mean(res: dict, metric: str, block: str = "overall", key: str | None = None) -> float | None:
    b = res["metrics"][block] if key is None else res["metrics"][block][key]
    return b[metric]["mean"]


def _f(x: float | None) -> str:
    return "–" if x is None else f"{x:.3f}"


def comparison(base: dict, loop: dict, base_ab: dict, loop_ab: dict) -> list[str]:
    lines = [f"| Metric | M3 `{BASE}` | M4 `{LOOP}` |", "|---|---|---|"]
    lines += [f"| {label} | {_f(_mean(base, m))} | {_f(_mean(loop, m))} |" for m, label in ROWS]
    lines += [f"| Correct, text modality | {_f(_mean(base, 'correct', 'by_modality', 'text'))} | "
              f"{_f(_mean(loop, 'correct', 'by_modality', 'text'))} |",
              f"| **Abstention rate on `{ABSTENTION_SPLIT}`** | {_f(_mean(base_ab, 'abstained'))} | "
              f"**{_f(_mean(loop_ab, 'abstained'))}** |",
              f"| Avg retries / query (`{ANSWERABLE_SPLIT}`) | 0 | {loop['graph']['retries_mean']:.3f} |",
              f"| Avg retries / query (`{ABSTENTION_SPLIT}`) | 0 | {loop_ab['graph']['retries_mean']:.3f} |",
              f"| Median end-to-end ms (`{ANSWERABLE_SPLIT}`) | "
              f"{base['latency_ms_median']['retrieve'] + base['latency_ms_median']['generate']:.0f} | "
              f"{loop['graph']['graph_ms_median']:.0f} |"]
    return lines


def slice_table(base: dict, loop: dict) -> list[str]:
    lines = ["| Slice | n | Correct M3 | Correct M4 | False-abst M3 | False-abst M4 |", "|---|---|---|---|---|---|"]
    for block in ("by_type", "by_modality"):
        for key, cell in loop["metrics"][block].items():
            lines.append(f"| {key} | {cell['correct']['n']} | {_f(_mean(base, 'correct', block, key))} | "
                         f"{_f(_mean(loop, 'correct', block, key))} | {_f(_mean(base, 'abstained', block, key))} | "
                         f"{_f(_mean(loop, 'abstained', block, key))} |")
    return lines


def loop_stats(name: str, res: dict) -> str:
    g = res["graph"]
    return (f"- `{name}`: retries histogram {g['retries_histogram']}, queries over the retry limit: "
            f"**{g['queries_over_retry_limit']}**, abstained by grader {g['abstained_by']['grader']}, "
            f"by generator {g['abstained_by']['generator']}.")


def paired(base: dict, loop: dict) -> list[str]:
    """Per-query outcome changes on the answerable split, so a net gain cannot hide losses."""
    b = {r["query_id"]: r["correct"] for r in base["per_query"]}
    flips = [(b[r["query_id"]], r["correct"]) for r in loop["per_query"]]
    return [f"- Wrong/refused in M3, correct in M4: **{sum(x == 0 and y == 1 for x, y in flips)}**",
            f"- Correct in M3, wrong/refused in M4: **{sum(x == 1 and y == 0 for x, y in flips)}**"]


def _queries(rec: dict) -> list[str]:
    return [t["query"] for t in rec["trace"] if t["node"] == "retrieve"]


def _grades(rec: dict) -> list[dict]:
    return [t for t in rec["trace"] if t["node"] == "grade"]


def rescues(loop: dict) -> tuple[int, list[str]]:
    """First grade insufficient, then answered and judged correct. Cases where gold was missing from the first
    top-5 and present in the final one come first: there the rewrite fixed retrieval, not just the grader's mind."""
    cands = [r for r in loop["per_query"] if r["retries"] > 0 and r["correct"] == 1]
    cands.sort(key=lambda r: (-(r["first_recall@5"] == 0 and r["recall@5"] == 1), r["query_id"]))
    out = []
    for r in cands[:N_EXAMPLES]:
        g = _grades(r)
        out += [f"### `{r['query_id']}` ({r['type']}, {r['source']})", "",
                f"- **Question:** {r['query']}",
                f"- **Attempt 1 grade:** insufficient: {g[0]['reason']}",
                *[f"- **Rewrite {i}:** `{q}`" for i, q in enumerate(_queries(r)[1:], 1)],
                f"- **Gold in top-5:** first attempt {'yes' if r['first_recall@5'] else 'no'}, "
                f"final {'yes' if r['recall@5'] else 'no'} (MRR {r['first_mrr']:.2f} → {r['mrr']:.2f})",
                f"- **Answer:** {r['answer']}", f"- **Reference:** {r['reference']}", ""]
    return len(cands), out


def abstentions(loop_ab: dict) -> list[str]:
    picks = sorted((r for r in loop_ab["per_query"] if r["abstained"] == 1.0),
                   key=lambda r: (r["abstained_by"] != "grader", -r["retries"], r["query_id"]))[:N_EXAMPLES]
    out = []
    for r in picks:
        out += [f"### `{r['query_id']}` ({r['abstained_by']} abstained after {r['retries']} retries)", "",
                f"- **Question:** {r['query']}",
                *[f"- **Query {i}:** `{q}`" for i, q in enumerate(_queries(r), 1)],
                f"- **Response:** {r['answer']}", ""]
    return out


def build() -> str:
    base, loop = _load(BASE, ANSWERABLE_SPLIT), _load(LOOP, ANSWERABLE_SPLIT)
    base_ab, loop_ab = _load(BASE, ABSTENTION_SPLIT), _load(LOOP, ABSTENTION_SPLIT)
    n_rescued, rescue_lines = rescues(loop)
    return "\n".join([
        "# M4: corrective loop vs M3", "",
        f"Sources: `results/{BASE}_*.json`, `results/{LOOP}_*.json`. Generator and judge `{loop['generator_model']}`, "
        f"M4 commit `{loop['git']['commit']}`{' (dirty)' if loop['git']['dirty'] else ''}. "
        f"Context metrics are on the hits the answer was generated from (M4: the final attempt).", "",
        *comparison(base, loop, base_ab, loop_ab), "",
        "## By slice (`dev_sample`)", "", *slice_table(base, loop), "",
        "## Loop behaviour", "", loop_stats(ANSWERABLE_SPLIT, loop), loop_stats(ABSTENTION_SPLIT, loop_ab), "",
        "## Paired per-query changes (`dev_sample`, correctness)", "", *paired(base, loop), "",
        f"## Rescued first retrievals ({n_rescued} answerable questions graded insufficient first, then answered "
        f"correctly; {N_EXAMPLES} shown)", "", *rescue_lines,
        f"## Correct abstentions ({N_EXAMPLES} shown)", "", *abstentions(loop_ab),
    ])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    text = build()
    (RESULTS_DIR / "m4_report.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
