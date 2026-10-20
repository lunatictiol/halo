"""M5 report: citations + grounding check vs M4 v2 (same retrieval and grades, replayed; D33), citation stats,
removed-sentence examples and 10 cited answers for manual review.

    uv run python -m eval.report.m5_report               # cite-v1 run -> results/m5_report.md
    uv run python -m eval.report.m5_report m5_cite_v2    # -> results/m5_cite_v2_report.md (v1 shown alongside)
"""

import json
import random
import sys

from eval.report.m4_report import _f, _load, _mean
from eval.report.summary import ABSTENTION_SPLIT, ANSWERABLE_SPLIT
from eval.results import RESULTS_DIR
from halo.data import data_dir

BASE, V1 = "m4_graph_v2", "m5_cite"
CITE = sys.argv[1] if len(sys.argv) > 1 else V1
N_REVIEW, N_REMOVED, REVIEW_SEED, EXCERPT = 10, 5, 5, 400
ROWS = [("correct", "Correct"), ("correct_if_answered", "Correct|ans"), ("faithful", "Faithful (final answer)"),
        ("faithful_raw", "Faithful (pre-check answer)"), ("abstained", "False-abstention")]
CITE_ROWS = [("citation_validity", "Citation validity (self-checked, pre-check answer)"),
             ("citation_coverage", "Citation coverage (pre-check answer)"),
             ("citation_coverage_final", "Citation coverage (final answer)"),
             ("sentences_removed", "Share of sentences removed")]


def _cell(res: dict, metric: str) -> str:
    return _f(_mean(res, metric)) if metric in res["metrics"]["overall"] else "–"


def comparison(runs: dict[str, tuple[dict, dict]]) -> list[str]:
    """runs: name -> (answerable results, abstention results), in column order."""
    ans, ab = [r[0] for r in runs.values()], [r[1] for r in runs.values()]

    def row(label: str, cells: list[str]) -> str:
        return f"| {label} | " + " | ".join(cells) + " |"
    lines = [row("Metric", [f"`{n}`" for n in runs]), "|---" * (len(runs) + 1) + "|"]
    lines += [row(label, [_cell(r, m) for r in ans]) for m, label in ROWS + CITE_ROWS]
    lines += [row(f"**Abstention rate on `{ABSTENTION_SPLIT}`**", [f"**{_cell(r, 'abstained')}**" for r in ab]),
              row(f"Faithful, answered `{ABSTENTION_SPLIT}` questions", [_cell(r, "faithful") for r in ab]),
              row(f"Median end-to-end ms (`{ANSWERABLE_SPLIT}`; M5 stitched)",
                  [f"{r['graph']['graph_ms_median']:.0f}" for r in ans]),
              row(f"Median generate ms (`{ANSWERABLE_SPLIT}`)", [f"{r['latency_ms_median']['generate']:.0f}" for r in ans])]
    return lines


def slice_table(cite: dict) -> list[str]:
    lines = ["| Slice | n | Validity | Coverage | Removed | Faithful pre → post |", "|---|---|---|---|---|---|"]
    for block in ("by_type", "by_modality"):
        for key, cell in cite["metrics"][block].items():
            lines.append(f"| {key} | {cell['citation_validity']['n']} | {_f(cell['citation_validity']['mean'])} | "
                         f"{_f(cell['citation_coverage']['mean'])} | {_f(cell['sentences_removed']['mean'])} | "
                         f"{_f(cell['faithful_raw']['mean'])} → {_f(cell['faithful']['mean'])} |")
    return lines


def totals(name: str, res: dict) -> str:
    t, a = res["citations"], res["graph"]["abstained_by"]
    return (f"- `{name}`: {t['answers_checked']} answers checked, {t['sentences']} sentences "
            f"({t['sentences_cited']} cited, {t['sentences_removed']} removed), {t['citations']} citations: "
            f"{t['supported']} supported, {t['unsupported']} unsupported, {t['out_of_range']} out of range, "
            f"{t['check_errors']} checker errors; {t.get('reattributed', 0)} sentences re-attributed. Abstained by grader {a['grader']}, generator {a['generator']}, "
            f"**grounding check {a['grounding']}**.")


def paired(base: dict, cite: dict) -> list[str]:
    b = {r["query_id"]: r["correct"] for r in base["per_query"]}
    flips = [(b[r["query_id"]], r["correct"]) for r in cite["per_query"]]
    return [f"- Wrong/refused in M4, correct in M5: **{sum(x == 0 and y == 1 for x, y in flips)}**",
            f"- Correct in M4, wrong/refused in M5: **{sum(x == 1 and y == 0 for x, y in flips)}**"]


def with_hits(res: dict) -> list[dict]:
    """Attach the context passages from the run checkpoint (results files keep only (paper, section, page))."""
    path = data_dir(res["config"]) / "runs" / res["run"] / "graph.jsonl"
    hits = {(r := json.loads(line))["query_id"]: r["hits"] for line in path.read_text(encoding="utf-8").splitlines()
            if line}
    return [r | {"hits": hits[r["query_id"]]} for r in res["per_query"]]


def _excerpt(rec: dict, n: int) -> str:
    text = " ".join(rec["hits"][n - 1]["text"].split())
    return text[:EXCERPT] + ("…" if len(text) > EXCERPT else "")


def _answer_block(rec: dict, title: str) -> list[str]:
    out = [f"### {title}: `{rec['query_id']}` ({rec['type']}, {rec['source']})", "",
           f"- **Question:** {rec['query']}", f"- **Final answer:** {rec['answer']}",
           f"- **Reference:** {rec['reference']}",
           f"- **Judge:** faithful {_f(rec['faithful'])}, correct {_f(rec['correct'])}", "- **Sentences:**"]
    for s in rec["grounding"]["sentences"]:
        out.append(f"  - ({'kept' if s['kept'] else 'REMOVED'}{', uncited' if not s['cites'] else ''}) {s['text']}")
        for c in s["cites"]:
            if c["verdict"] == "out_of_range":
                out.append(f"    - `[{c['n']}]` out of range")
                continue
            out += [f"    - `[{c['n']}]` {c['label']} → **{c['verdict']}**: {c['reason']}",
                    f"      > {_excerpt(rec, c['n'])}"]
        if m := s.get("reattributed"):
            out += [f"    - re-attributed to `[{m['n']}]` {m['label']} → **supported**: {m['reason']}",
                    f"      > {_excerpt(rec, m['n'])}"]
    return out + ["- **Your verdict:** citations valid? [ ] yes [ ] no; notes:", ""]


def review_sample(recs: list[dict]) -> list[str]:
    pool = sorted((r for r in recs if r["grounding"] and not r["abstained"]), key=lambda r: r["query_id"])
    out = []
    for i, r in enumerate(random.Random(REVIEW_SEED).sample(pool, min(N_REVIEW, len(pool))), 1):
        out += _answer_block(r, f"Review {i}")
    return out


def removed_examples(recs: list[dict]) -> tuple[int, list[str]]:
    cands = sorted((r for r in recs if r["grounding"] and any(not s["kept"] for s in r["grounding"]["sentences"])),
                   key=lambda r: r["query_id"])
    out = []
    for r in cands[:N_REMOVED]:
        out += _answer_block(r, "Removed")[:-1] + [f"- **Pre-check answer:** {r['grounding']['raw']}", ""]
    return len(cands), out


def build() -> str:
    names = [BASE] + ([V1] if CITE != V1 else []) + [CITE]
    runs = {n: (_load(n, ANSWERABLE_SPLIT), _load(n, ABSTENTION_SPLIT)) for n in names}
    (base, _), (cite, cite_ab) = runs[BASE], runs[CITE]
    recs = with_hits(cite)
    n_removed, removed_lines = removed_examples(recs)
    src, c = cite["replayed_from"], cite["config"]["cite"]
    return "\n".join([
        "# M5: citations and grounding check vs M4", "",
        f"Sources: `results/{BASE}_*.json`, `results/{CITE}_*.json`. M5 replays `{src['run']}` (commit "
        f"`{src['git']['commit']}`): same hits and grader decisions; only generation (`{c['prompt_version']}`) and "
        f"the grounding check (`{c['check_prompt_version']}`) rerun (D33). Generator, checker and judge "
        f"`{cite['generator_model']}`; M5 commit `{cite['git']['commit']}`{' (dirty)' if cite['git']['dirty'] else ''}. "
        "Citation validity is the checker's own verdicts on the pre-check answer, not an independent judge.", "",
        *comparison(runs), "",
        "## Citation totals", "", totals(ANSWERABLE_SPLIT, cite), totals(ABSTENTION_SPLIT, cite_ab), "",
        f"## By slice (`{ANSWERABLE_SPLIT}`)", "", *slice_table(cite), "",
        f"## Paired per-query changes (`{ANSWERABLE_SPLIT}`, correctness)", "", *paired(base, cite), "",
        f"## Answers where the check removed a sentence ({n_removed} on `{ANSWERABLE_SPLIT}`; "
        f"{min(N_REMOVED, n_removed)} shown)", "", *removed_lines,
        f"## {N_REVIEW} cited answers for manual review (seeded sample of answered `{ANSWERABLE_SPLIT}` questions)", "",
        *review_sample(recs),
    ])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    text = build()
    (RESULTS_DIR / ("m5_report.md" if CITE == V1 else f"{CITE}_report.md")).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
