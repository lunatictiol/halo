"""M8 regression gate on deterministic retrieval metrics (D40).

    uv run python -m eval.runners.ci run                     # local: retrieval-only on [ci] split, ~7 min, needs Ollama
    uv run python -m eval.runners.ci run --update-baseline   # also make this run the committed baseline
    uv run python -m eval.runners.ci check                   # CI: no index, no models, only git + the results file

The index and Ollama are not available on a hosted runner, so CI checks a committed results file instead of
re-running retrieval. `check` fails when the file is stale (made from a dirty tree, from a commit that is not an
ancestor of HEAD, or with code/config under [ci] watch changed since), when its summary does not match its
per-query records, or when a metric dropped more than [ci] max_drop below the baseline.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from eval.metrics.retrieval import gold_rank, recall_at_k, reciprocal_rank
from eval.results import RESULTS_DIR
from halo.config import ROOT, load_config


def recompute(per_query: list[dict], metrics: list[str]) -> dict[str, float]:
    """Metric means from the per-query rankings, so a hand-edited summary cannot pass."""
    ranks = [gold_rank([tuple(s) for s in p["retrieved"]], tuple(p["gold"])) for p in per_query]

    def value(m: str, rank: int | None) -> float:
        if m == "mrr":
            return reciprocal_rank(rank)
        if m.startswith("recall@"):
            return recall_at_k(rank, int(m.split("@")[1]))
        raise ValueError(f"[ci] metric {m!r} is not supported; use mrr or recall@k")

    return {m: sum(value(m, r) for r in ranks) / len(ranks) for m in metrics}


def verify_summary(run: dict, recomputed: dict[str, float], metrics: list[str]) -> list[str]:
    stored = run["metrics"]["overall"]
    return [f"{m}: summary says {stored[m]['mean']} but per-query records give {recomputed[m]:.4f}"
            for m in metrics if abs(stored[m]["mean"] - recomputed[m]) > 1e-4]  # summary is rounded to 4 places


def compare(current: dict[str, float], baseline: dict[str, float], ci: dict) -> list[str]:
    return [f"{m}: {current[m]:.4f} is {baseline[m] - current[m]:.4f} below baseline {baseline[m]:.4f} "
            f"(max drop {ci['max_drop']})" for m in ci["metrics"] if baseline[m] - current[m] > ci["max_drop"]]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=root, check=False)


def stale(git: dict, watch: list[str], root: Path = ROOT) -> list[str]:
    """Reasons the results file does not describe the code at HEAD."""
    if git["dirty"]:
        return ["results were produced from a dirty tree; commit first, then re-run `ci run`"]
    commit = git["commit"]
    if _git(root, "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        return [f"results commit {commit} is not an ancestor of HEAD; re-run `ci run`"]
    changed = _git(root, "diff", "--name-only", commit, "HEAD", "--", *watch).stdout.split()
    if changed:
        return [f"changed since results commit {commit} without re-running `ci run`: {', '.join(changed)}"]
    return []


def _load(name: str) -> dict:
    return json.loads((RESULTS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def check(cfg: dict) -> int:
    ci = cfg["ci"]
    run, baseline = _load(ci["results"]), _load(ci["baseline"])
    current = recompute(run["per_query"], ci["metrics"])
    failures = stale(run["git"], ci["watch"]) + verify_summary(run, current, ci["metrics"])
    if run["config"] != cfg:
        failures.append("results config differs from config/default.toml at HEAD")
    failures += compare(current, baseline["metrics"], ci)
    print(f"results {ci['results']} @ {run['git']['commit']}  vs  baseline {ci['baseline']} @ {baseline['commit']}")
    for m in ci["metrics"]:
        print(f"  {m:<10} {current[m]:.4f}  baseline {baseline['metrics'][m]:.4f}  "
              f"delta {current[m] - baseline['metrics'][m]:+.4f}")
    for f in failures:
        print(f"FAIL {f}")
    print("regression gate:", "FAILED" if failures else "passed")
    return 1 if failures else 0


def run(cfg: dict, update_baseline: bool) -> None:
    from eval.runners.ablation import evaluate  # heavy imports (torch, qdrant) only for the local run

    ci = cfg["ci"]
    res = evaluate(cfg["retrieve"]["method"], ci["split"], cfg, name=ci["results"])
    if res["git"]["dirty"]:
        print("warning: tree is dirty, `ci check` will reject this file; commit and re-run", file=sys.stderr)
    if update_baseline:
        doc = {"source": ci["results"], "commit": res["git"]["commit"], "split": ci["split"],
               "method": res["method"], "collection": cfg["retrieve"]["collection"], "n_queries": res["n_queries"],
               "metrics": recompute(res["per_query"], ci["metrics"])}
        out = RESULTS_DIR / f"{ci['baseline']}.json"
        out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"wrote baseline {out}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["run", "check"])
    p.add_argument("--update-baseline", action="store_true")
    a = p.parse_args()
    cfg = load_config()
    if a.command == "run":
        run(cfg, a.update_baseline)
    else:
        sys.exit(check(cfg))


if __name__ == "__main__":
    main()
