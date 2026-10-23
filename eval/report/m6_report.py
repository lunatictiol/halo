"""M6 report: why metrics move from the 100-paper dev index to the 980-paper full index.

    uv run python -m eval.report.m6_report        # -> results/m6_report.md

Two comparisons, each holding everything else fixed:
- Index size: m5_check_v2 (dev index) vs m6_graph (full index), same pipeline, same questions.
- Question set: inside the single m6_graph full run, dev_sample questions vs the other answerable questions.
"""

from collections import Counter

from eval.report.m4_report import _load
from eval.report.summary import ABSTENTION_SPLIT, ANSWERABLE_SPLIT
from eval.results import RESULTS_DIR
from halo.data import load_hf, load_split

DEV, FINAL = "m5_check_v2", "m6_graph"
MODALITIES = ("text", "text-image", "text-table", "text-table-image")


def _rate(rows: list[dict], metric: str) -> str:
    vals = [r[metric] for r in rows if r.get(metric) is not None]
    return f"{sum(vals) / len(vals):.3f} (n={len(vals)})" if vals else "–"


def question_set(full: dict, dev_qids: set[str]) -> list[str]:
    dev = [r for r in full["per_query"] if r["query_id"] in dev_qids]
    rest = [r for r in full["per_query"] if r["query_id"] not in dev_qids]
    lines = ["## Same run, same index: dev_sample questions vs the rest of `full`", "",
             "| Slice | dev_sample questions | other questions |", "|---|---|---|"]
    for m in ("recall@5", "mrr", "correct", "correct_if_answered", "abstained", "faithful"):
        lines.append(f"| {m} | {_rate(dev, m)} | {_rate(rest, m)} |")
    for mod in MODALITIES:
        lines.append(f"| correct, {mod} | {_rate([r for r in dev if r['source'] == mod], 'correct')} | "
                     f"{_rate([r for r in rest if r['source'] == mod], 'correct')} |")
    for hit in (1.0, 0.0):
        label = "gold in top-5" if hit else "gold not in top-5"
        lines.append(f"| correct, {label} | {_rate([r for r in dev if r['recall@5'] == hit], 'correct')} | "
                     f"{_rate([r for r in rest if r['recall@5'] == hit], 'correct')} |")
    wrong = [r for r in rest if r.get("correct") == 0.0]
    why = Counter("abstained" if r["abstained"] else "answered, gold in top-5" if r["recall@5"] == 1.0
                  else "answered, gold not in top-5" for r in wrong)
    lines += ["", f"Wrong answers among the other questions ({len(wrong)}): "
              + ", ".join(f"{k} {v}" for k, v in why.most_common()) + "."]
    return lines


def abstention(dev_ab: dict, full_ab: dict, sources: set[str], dev_papers: set[str]) -> list[str]:
    dev_by = {r["query_id"]: r for r in dev_ab["per_query"]}
    answered = [r for r in full_ab["per_query"] if not r["abstained"]]
    both = sum(1 for r in answered if not dev_by[r["query_id"]]["abstained"])
    top = Counter("dev_slice paper" if r["retrieved"][0][0] in dev_papers
                  else "other source paper" if r["retrieved"][0][0] in sources else "official distractor"
                  for r in answered)
    first = Counter(next(t["verdict"] for t in r["trace"] if t["node"] == "grade") for r in answered)
    return ["## Abstention: same 152 questions, dev index vs full index", "",
            f"- Answered instead of abstaining: dev index {sum(1 for r in dev_ab['per_query'] if not r['abstained'])}"
            f", full index {len(answered)} ({both} answered on both).",
            "- Paper of the top-ranked passage for the full-index answers: "
            + ", ".join(f"{k} {v}" for k, v in top.most_common()) + ".",
            "- First grade for those answers: " + ", ".join(f"{k} {v}" for k, v in first.most_common()) + "."]


def main() -> None:
    full, full_ab, dev_ab = _load(FINAL, "full"), _load(FINAL, ABSTENTION_SPLIT), _load(DEV, ABSTENTION_SPLIT)
    dev_qids = set(load_split(ANSWERABLE_SPLIT)["query_ids"])
    sources = {q["doc_id"] for q in load_hf("qrels.json").values()}
    dev_papers = set(load_split("dev_slice")["paper_ids"])
    lines = ["# M6 report: dev index vs full index", "", f"Runs: `{DEV}_*` (100-paper dev index), `{FINAL}_*` "
             "(980-paper full index). Same pipeline, generator and judge (`qwen3:8b`).", "",
             *question_set(full, dev_qids), "", *abstention(dev_ab, full_ab, sources, dev_papers), ""]
    out = RESULTS_DIR / "m6_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
