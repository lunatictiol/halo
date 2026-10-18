"""Print the summary table for a run (overall / per question type / per modality) and save it as markdown.

    uv run python -m eval.report.summary --name m2_baseline
"""

import argparse
import json
import sys

from eval.results import RESULTS_DIR

ANSWERABLE_SPLIT, ABSTENTION_SPLIT = "dev_sample", "abstention_set"
COLUMNS = [("recall@5", "R@5"), ("recall@10", "R@10"), ("mrr", "MRR"), ("ndcg@10", "nDCG@10"),
           ("paper_hit@10", "Paper@10"), ("faithful", "Faithful"), ("correct", "Correct"),
           ("correct_if_answered", "Correct|ans"), ("abstained", "False-abst")]


def _fmt(cell: dict) -> str:
    return "–" if cell["mean"] is None else f"{cell['mean']:.3f}"


def _row(label: str, block: dict) -> str:
    n = block[COLUMNS[0][0]]["n"]
    return f"| {label} | {n} | " + " | ".join(_fmt(block[m]) for m, _ in COLUMNS) + " |"


def answerable_table(res: dict) -> list[str]:
    m = res["metrics"]
    lines = ["| Slice | n | " + " | ".join(h for _, h in COLUMNS) + " |", "|---" * (len(COLUMNS) + 2) + "|",
             _row("**overall**", m["overall"])]
    lines += [_row(f"type: {k}", v) for k, v in m["by_type"].items()]
    lines += [_row(f"modality: {k}", v) for k, v in m["by_modality"].items()]
    return lines


def abstention_lines(res: dict) -> list[str]:
    o = res["metrics"]["overall"]
    return [f"- Abstention rate on `{ABSTENTION_SPLIT}`: **{_fmt(o['abstained'])}** (n={o['abstained']['n']})",
            f"- Answered abstention questions judged *supported* by retrieved context (spot-check candidates): "
            f"{len(res['abstention_spot_check'])}"]


def build(name: str) -> str:
    ans = json.loads((RESULTS_DIR / f"{name}_{ANSWERABLE_SPLIT}.json").read_text(encoding="utf-8"))
    abst = json.loads((RESULTS_DIR / f"{name}_{ABSTENTION_SPLIT}.json").read_text(encoding="utf-8"))
    lat = ans["latency_ms_median"]
    return "\n".join([
        f"# {name}: summary",
        "",
        f"Generator `{ans['generator_model']}`, judge `{ans['judge_model']}`, commit `{ans['git']['commit']}`"
        f"{' (dirty)' if ans['git']['dirty'] else ''}. Source files: `results/{name}_{ANSWERABLE_SPLIT}.json`, "
        f"`results/{name}_{ABSTENTION_SPLIT}.json`.",
        "",
        f"## `{ANSWERABLE_SPLIT}` (answerable)",
        "",
        *answerable_table(ans),
        "",
        "False-abst = share of answerable questions the model refused. Correct counts a refusal as wrong; "
        "Correct|ans is over answered questions only. Faithful is over answered questions only.",
        "",
        f"Median latency per query: retrieve {lat['retrieve']} ms, generate {lat['generate']} ms. "
        f"Judge errors: {ans['judge_errors']}/{ans['judge_calls']}.",
        "",
        "## Abstention",
        "",
        *abstention_lines(abst),
        "",
    ])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="m2_baseline")
    name = p.parse_args().name
    text = build(name)
    (RESULTS_DIR / f"{name}_summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
