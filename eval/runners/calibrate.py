"""M7 judge calibration: blind human labels vs each judge on a seeded sample of saved M6 answers (D39).

    uv run python -m eval.runners.calibrate sample   # writes the sample, a blank label sheet and labels CSV
    uv run python -m eval.runners.calibrate judge    # runs every [calibration] judge on the sample (resumable)
    uv run python -m eval.runners.calibrate report   # agreement + kappa, once every label is filled in

The sheet shows no judge verdicts, so the human labels are independent of both judges. Judges see exactly the
inputs the M6 eval judge saw: the final answer, the top-k_context passages it was generated from, the reference.
"""

import argparse
import csv
import json
import random
from pathlib import Path

from eval.judge import CORRECTNESS, FAITHFULNESS, judge_correctness, judge_faithfulness, with_judge
from eval.metrics.agreement import agreement
from eval.results import RESULTS_DIR, write_results
from halo.config import ROOT, load_config
from halo.data import data_dir
from halo.generate.baseline import format_context

CAL_DIR = ROOT / "eval" / "calibration"
SAMPLE, LABELS, SHEET = CAL_DIR / "m7_sample.json", CAL_DIR / "m7_labels.csv", CAL_DIR / "m7_sheet.md"
LABELS_OF = {"faithfulness": FAITHFULNESS, "correctness": CORRECTNESS}
CHUNK_FIELDS = ("paper_id", "section_id", "section_title", "page", "text")


def _pool(run: str, kind: str, cfg: dict) -> list[dict]:
    """Judged, non-abstained answers of one saved run, with the local judge's verdict (used only to stratify)."""
    recs = json.loads((RESULTS_DIR / f"{run}.json").read_text(encoding="utf-8"))["per_query"]
    hits = {}
    if kind == "faithfulness":
        graph = (data_dir(cfg) / "runs" / run / "graph.jsonl").read_text(encoding="utf-8").splitlines()
        k = cfg["retrieve"]["k_context"]
        hits = {(g := json.loads(line))["query_id"]: [{f: h[f] for f in CHUNK_FIELDS} for h in g["hits"][:k]]
                for line in graph if line}
    out = []
    for r in recs:
        if not r[kind] or r[kind]["verdict"] is None:
            continue
        item = {"kind": kind, "run": run, "query_id": r["query_id"], "type": r["type"], "source": r["source"],
                "question": r["query"], "answer": r["answer"], "_negative": r[kind]["verdict"] == LABELS_OF[kind][1]}
        item |= {"chunks": hits[r["query_id"]]} if kind == "faithfulness" else {"reference": r["reference"]}
        out.append(item)
    return sorted(out, key=lambda x: (x["run"], x["query_id"]))


def draw(pool: list[dict], per_kind: int, negative_share: float, rng: random.Random) -> list[dict]:
    """Up to negative_share negatives (all of them if fewer exist), positives for the rest."""
    neg = [x for x in pool if x["_negative"]]
    pos = [x for x in pool if not x["_negative"]]
    n_neg = min(len(neg), round(per_kind * negative_share))
    return rng.sample(neg, n_neg) + rng.sample(pos, per_kind - n_neg)


def build_sample(cfg: dict) -> list[dict]:
    c = cfg["calibration"]
    rng = random.Random(c["seed"])
    items = []
    for kind in ("faithfulness", "correctness"):
        pool = [x for run in c[f"{kind}_runs"] for x in _pool(run, kind, cfg)]
        picked = draw(pool, c["per_kind"], c["negative_share"], rng)
        rng.shuffle(picked)  # negatives must not cluster: the labeler would learn the sampling
        items += [{"item_id": f"{kind[0]}{i:02d}"} | {k: v for k, v in x.items() if k != "_negative"}
                  for i, x in enumerate(picked, 1)]
    return items


RUBRIC = """Label each item yourself before looking at any judge output. Use the same rubric the judges get:

- **faithfulness** — `supported`: every factual claim in the answer is stated in, or directly inferable from, \
the context. `unsupported`: at least one claim is absent from or contradicts the context. Judge support only, \
not correctness.
- **correctness** — `correct`: the answer conveys the key facts of the reference and does not contradict it \
(different wording, extra detail or omitting secondary details is fine). `incorrect`: it misses the main point, \
contradicts the reference, or answers a different question.

Write the label in the `human` column of `m7_labels.csv` (optional `note`)."""


def write_sheet(items: list[dict]) -> None:
    parts = ["# M7 calibration sheet: label blind\n", RUBRIC, ""]
    for it in items:
        parts += [f"## {it['item_id']} · {it['kind']}  ({it['type']}, {it['source']})", "",
                  f"**Question:** {it['question']}", "", f"**Answer:** {it['answer']}", ""]
        if it["kind"] == "correctness":
            parts += [f"**Reference:** {it['reference']}", ""]
        else:
            parts += ["<details><summary>Context</summary>", "", "```", format_context(it["chunks"]), "```", "",
                      "</details>", ""]
    SHEET.write_text("\n".join(parts), encoding="utf-8")


def cmd_sample(cfg: dict) -> None:
    CAL_DIR.mkdir(parents=True, exist_ok=True)
    items = build_sample(cfg)
    SAMPLE.write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    write_sheet(items)
    if LABELS.exists():  # never overwrite hand labels
        print(f"kept existing {LABELS.name}")
    else:
        with LABELS.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["item_id", "kind", "human", "note"])
            w.writerows([it["item_id"], it["kind"], "", ""] for it in items)
    print(f"{len(items)} items -> {SAMPLE.name}, {SHEET.name}, {LABELS.name}")


def verdicts_path(name: str) -> Path:
    return CAL_DIR / f"m7_verdicts_{name}.jsonl"


def _read(path: Path) -> dict[str, dict]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return {(r := json.loads(line))["item_id"]: r for line in lines if line}


def cmd_judge(cfg: dict) -> None:
    items = json.loads(SAMPLE.read_text(encoding="utf-8"))
    for name in cfg["calibration"]["judges"]:
        jcfg, path = with_judge(cfg, name), verdicts_path(name)
        done = _read(path)
        for it in (x for x in items if x["item_id"] not in done):
            v = (judge_faithfulness(it["question"], it["answer"], it["chunks"], jcfg) if it["kind"] == "faithfulness"
                 else judge_correctness(it["question"], it["answer"], it["reference"], jcfg))
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"item_id": it["item_id"], "model": jcfg["judge"]["model"]} | v,
                                   ensure_ascii=False) + "\n")
        print(f"{name}: {len(_read(path))}/{len(items)} judged")


def read_labels(items: list[dict]) -> dict[str, str]:
    with LABELS.open(encoding="utf-8") as f:
        rows = {r["item_id"]: r["human"].strip().lower() for r in csv.DictReader(f)}
    kinds = {it["item_id"]: it["kind"] for it in items}
    bad = [i for i in kinds if rows.get(i) not in LABELS_OF[kinds[i]]]
    if bad:
        raise SystemExit(f"{len(bad)} items unlabeled or with an invalid label: {', '.join(bad[:10])}")
    return rows


def calibration(items: list[dict], human: dict[str, str], judged: dict[str, dict[str, dict]]) -> dict:
    """Per kind: each judge vs human, and judge vs judge."""
    names = list(judged)
    out = {}
    for kind in ("faithfulness", "correctness"):
        ids = [it["item_id"] for it in items if it["kind"] == kind]
        h = [human[i] for i in ids]
        v = {n: [judged[n].get(i, {}).get("verdict") for i in ids] for n in names}
        out[kind] = {f"{n}_vs_human": agreement(v[n], h) for n in names}
        out[kind] |= {f"{a}_vs_{b}": agreement(v[a], v[b]) for i, a in enumerate(names) for b in names[i + 1:]}
        out[kind]["human_negatives"] = sum(x == LABELS_OF[kind][1] for x in h)
    return out


def cmd_report(cfg: dict) -> None:
    items = json.loads(SAMPLE.read_text(encoding="utf-8"))
    human = read_labels(items)
    judged = {n: _read(verdicts_path(n)) for n in cfg["calibration"]["judges"]}
    models = {n: with_judge(cfg, n)["judge"]["model"] for n in judged}
    cal = calibration(items, human, judged)
    disagreements = [{"item_id": it["item_id"], "kind": it["kind"], "human": human[it["item_id"]]}
                     | {n: judged[n][it["item_id"]]["verdict"] for n in judged}
                     | {f"{n}_reason": judged[n][it["item_id"]]["reason"] for n in judged}
                     for it in items if any(judged[n][it["item_id"]]["verdict"] != human[it["item_id"]] for n in judged)]
    conf = confusion(items, human, judged)
    out = write_results("m7_judge_calibration", {"judges": models, "n_items": len(items), "calibration": cal,
                                                 "confusion": conf, "disagreements": disagreements}, cfg)
    md = out.with_suffix(".md")
    md.write_text(to_markdown(models, cal, conf, out.name), encoding="utf-8")
    print(f"wrote {out} and {md.name}")


def confusion(items: list[dict], human: dict[str, str], judged: dict[str, dict[str, dict]]) -> dict:
    """Per kind and judge: count of (judge verdict, human label) pairs, keyed 'judge->human'."""
    out = {}
    for kind in ("faithfulness", "correctness"):
        ids = [it["item_id"] for it in items if it["kind"] == kind]
        out[kind] = {n: {f"{j}->{h}": sum(judged[n][i]["verdict"] == j and human[i] == h for i in ids)
                         for j in LABELS_OF[kind] for h in LABELS_OF[kind]} for n in judged}
    return out


def to_markdown(models: dict[str, str], cal: dict, conf: dict, source: str) -> str:
    lines = ["# M7 judge calibration", "",
             f"Generated from [`{source}`]({source}) by `eval.runners.calibrate report`. 25 faithfulness and 25 "
             "correctness items, labeled blind; negatives oversampled by the qwen verdict (D39), so agreement here "
             "is not the population agreement.", "",
             "| Kind | Judge | Model | n | Agreement | Cohen's κ |", "|---|---|---|---|---|---|"]
    for kind, block in cal.items():
        lines += [f"| {kind} | {n} | `{models[n]}` | {block[f'{n}_vs_human']['n']} | "
                  f"{block[f'{n}_vs_human']['agreement']} | {block[f'{n}_vs_human']['kappa']} |" for n in models]
    lines += ["", "Judge vs judge and human negatives:", ""]
    for kind, block in cal.items():
        pairs = ", ".join(f"{k.replace('_vs_', ' vs ')} κ {v['kappa']}" for k, v in block.items()
                          if isinstance(v, dict) and "human" not in k)
        lines.append(f"- **{kind}:** {pairs}; {block['human_negatives']} of 25 labeled negative by me.")
    lines += ["", "## Confusion (judge verdict → my label)", ""]
    for kind, by_judge in conf.items():
        cols = list(next(iter(by_judge.values())))
        lines += [f"**{kind}**", "", "| Judge | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        lines += [f"| {n} | " + " | ".join(str(c[k]) for k in cols) + " |" for n, c in by_judge.items()]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("sample", "judge", "report"))
    cfg = load_config()
    {"sample": cmd_sample, "judge": cmd_judge, "report": cmd_report}[p.parse_args().command](cfg)


if __name__ == "__main__":
    main()
