import subprocess

from eval.runners.ci import compare, recompute, stale, verify_summary

CI = {"metrics": ["recall@5", "mrr"], "max_drop": 0.005}
BASELINE = {"recall@5": 0.5, "mrr": 0.4167}


def _rec(rank: int | None) -> dict:
    """Gold is (p, 1); the gold chunk sits at `rank` (None = not retrieved) among 10 chunks."""
    ranked = [["x", 0]] * 10
    if rank is not None:
        ranked = ranked[:rank - 1] + [["p", 1]] + ranked[rank:]
    return {"gold": ["p", 1], "retrieved": ranked}


def _run(ranks: list[int | None]) -> dict:
    per_query = [_rec(r) for r in ranks]
    m = recompute(per_query, CI["metrics"])
    return {"per_query": per_query, "metrics": {"overall": {k: {"mean": round(v, 4)} for k, v in m.items()}}}


def _metrics(ranks: list[int | None]) -> dict:
    return recompute(_run(ranks)["per_query"], CI["metrics"])


def test_recompute_known_values():
    # ranks 1, 2, 6, missing: R@5 = 2/4, MRR = (1 + 1/2 + 1/6 + 0) / 4
    m = _metrics([1, 2, 6, None])
    assert m["recall@5"] == 0.5
    assert abs(m["mrr"] - (1 + 0.5 + 1 / 6) / 4) < 1e-12


def test_identical_run_passes():
    assert compare(_metrics([1, 2, 6, None]), BASELINE, CI) == []


def test_drop_beyond_tolerance_fails():
    fails = compare(_metrics([1, 6, 6, None]), BASELINE, CI)  # second query falls out of the top 5
    assert len(fails) == 2 and "recall@5" in fails[0] and "mrr" in fails[1]


def test_improvement_passes():
    assert compare(_metrics([1, 1, 1, 1]), BASELINE, CI) == []


def test_tampered_summary_fails():
    run = _run([1, 2, 6, None])
    run["metrics"]["overall"]["recall@5"]["mean"] = 0.9
    fails = verify_summary(run, recompute(run["per_query"], CI["metrics"]), CI["metrics"])
    assert fails and "recall@5" in fails[0]


def test_untampered_summary_passes():
    run = _run([1, 2, 6, None])
    assert verify_summary(run, recompute(run["per_query"], CI["metrics"]), CI["metrics"]) == []


def _repo(tmp_path):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "halo").mkdir()
    (tmp_path / "halo" / "x.py").write_text("a = 1\n")
    git("add", ".")
    git("commit", "-qm", "code")
    return git, git("rev-parse", "--short", "HEAD")


def test_stale_fresh_results_pass(tmp_path):
    git, commit = _repo(tmp_path)
    (tmp_path / "results.json").write_text("{}")  # a results-only commit after the run is fine
    git("add", ".")
    git("commit", "-qm", "results")
    assert stale({"commit": commit, "dirty": False}, ["halo"], tmp_path) == []


def test_stale_code_change_fails(tmp_path):
    git, commit = _repo(tmp_path)
    (tmp_path / "halo" / "x.py").write_text("a = 2\n")
    git("commit", "-qam", "change")
    fails = stale({"commit": commit, "dirty": False}, ["halo"], tmp_path)
    assert fails and "halo/x.py" in fails[0]


def test_stale_dirty_or_unknown_commit_fails(tmp_path):
    _, commit = _repo(tmp_path)
    assert stale({"commit": commit, "dirty": True}, ["halo"], tmp_path)
    assert stale({"commit": "deadbee", "dirty": False}, ["halo"], tmp_path)
