"""Run a retrieval method -> LLM answer on a split: retrieve -> generate -> judge -> score.

    uv run python -m eval.runners.run --split dev_sample                     # method from config
    uv run python -m eval.runners.run --split abstention_set --method dense --name m2_baseline
    uv run python -m eval.runners.run --split dev_sample --limit 5           # smoke test, separate run dir

Each stage checkpoints per query under data/runs/<run>/ so an interrupted run resumes, and judging can be
redone without regenerating. Checkpoints are tied to a config fingerprint; a changed config needs --fresh.
"""

import argparse
import hashlib
import json
import shutil
import statistics
import time
from pathlib import Path

from eval.judge import judge_correctness, judge_faithfulness
from eval.metrics.abstention import is_abstention
from eval.metrics.answer import answer_scores
from eval.metrics.retrieval import query_metrics
from eval.metrics.slices import summarize
from eval.results import RESULTS_DIR, write_results
from halo.config import load_config
from halo.data import data_dir, load_hf, load_split
from halo.generate.baseline import answer
from halo.retrieve import METHODS, Retriever

STAGES = ("retrieve", "generate", "judge", "score")
# Questions whose source paper is never indexed: the correct behaviour is to abstain (CLAUDE.md, Dataset).
ABSTENTION_SPLITS = {"abstention_set"}
HIT_KEYS = ("paper_id", "section_id", "section_title", "page", "chunk_idx", "score", "text")


def load_queries(split: str, cfg: dict) -> list[dict]:
    q, a, r = (load_hf(f, cfg) for f in ("queries.json", "answers.json", "qrels.json"))
    return [{"query_id": i, "query": q[i]["query"], "type": q[i]["type"], "source": q[i]["source"],
             "gold": [r[i]["doc_id"], r[i]["section_id"]], "reference": a[i]}
            for i in load_split(split)["query_ids"]]


def retrieve_all(queries: list[dict], cfg: dict) -> dict[str, dict]:
    """Top k_eval hits per query (with text, for generation), the full candidate ranking as (paper, section)
    pairs (for the recall@k_candidates ceiling), and per-stage latency."""
    r = cfg["retrieve"]
    retriever = Retriever(cfg)
    try:
        # Warm-up: loads the embedding model, BM25 index and reranker so query 1 is not billed for them.
        retriever.retrieve(queries[0]["query"], r["method"])
        out = {}
        for n, q in enumerate(queries, 1):
            start = time.perf_counter()
            hits, stage_ms = retriever.retrieve(q["query"], r["method"])
            out[q["query_id"]] = {"retrieve_ms": round((time.perf_counter() - start) * 1000), "stage_ms": stage_ms,
                                  "candidates": [[h["paper_id"], h["section_id"]] for h in hits],
                                  "hits": [{k: h[k] for k in HIT_KEYS} for h in hits[:r["k_eval"]]]}
            if n % 50 == 0 or n == len(queries):
                print(f"  retrieved {n}/{len(queries)}", flush=True)
        return out
    finally:
        retriever.close()
        if r["method"].endswith("_rerank"):
            from halo.retrieve.rerank import release
            release()


def _read_jsonl(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {(rec := json.loads(line))["query_id"]: rec for line in path.read_text(encoding="utf-8").splitlines() if line}


def _append_jsonl(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _pending(queries: list[dict], done: dict, stage: str) -> list[dict]:
    todo = [q for q in queries if q["query_id"] not in done]
    print(f"{stage}: {len(done)} done, {len(todo)} to go", flush=True)
    return todo


def generate_all(queries: list[dict], retrieved: dict, path: Path, cfg: dict) -> None:
    g, k = cfg["generate"], cfg["retrieve"]["k_context"]
    todo = _pending(queries, _read_jsonl(path), "generate")
    for n, q in enumerate(todo, 1):
        resp = answer(q["query"], retrieved[q["query_id"]]["hits"][:k], cfg)
        _append_jsonl(path, {"query_id": q["query_id"], "answer": resp["content"],
                             "abstained": is_abstention(resp["content"], g["sentinel"]),
                             "generate_ms": resp["ms"], "prompt_tokens": resp["prompt_tokens"],
                             "output_tokens": resp["output_tokens"]})
        if n % 10 == 0 or n == len(todo):
            print(f"  generated {n}/{len(todo)}", flush=True)


def judge_all(queries: list[dict], retrieved: dict, generated: dict, path: Path, cfg: dict, answerable: bool) -> None:
    """Faithfulness for every non-abstained answer; correctness only where a reference answer is valid."""
    k = cfg["retrieve"]["k_context"]
    todo = _pending(queries, _read_jsonl(path), "judge")
    for n, q in enumerate(todo, 1):
        gen, rec = generated[q["query_id"]], {"query_id": q["query_id"]}
        if not gen["abstained"]:
            chunks = retrieved[q["query_id"]]["hits"][:k]
            rec["faithfulness"] = judge_faithfulness(q["query"], gen["answer"], chunks, cfg)
            if answerable:
                rec["correctness"] = judge_correctness(q["query"], gen["answer"], q["reference"], cfg)
        _append_jsonl(path, rec)
        if n % 10 == 0 or n == len(todo):
            print(f"  judged {n}/{len(todo)}", flush=True)


def _verdict(judged: dict, key: str) -> str | None:
    return judged.get(key, {}).get("verdict")


def per_query_record(q: dict, ret: dict, gen: dict, jud: dict, cfg: dict, answerable: bool) -> dict:
    r = cfg["retrieve"]
    ranked = [(h["paper_id"], h["section_id"]) for h in ret["hits"]]
    scores = answer_scores(gen["abstained"], _verdict(jud, "faithfulness"), _verdict(jud, "correctness"))
    rec = {k: q[k] for k in ("query_id", "type", "source", "query", "gold", "reference")}
    rec |= {"answer": gen["answer"], "faithfulness": jud.get("faithfulness"), "correctness": jud.get("correctness"),
            "retrieved": [[h["paper_id"], h["section_id"], h["page"]] for h in ret["hits"]],
            "retrieve_ms": ret["retrieve_ms"], "generate_ms": gen["generate_ms"]}
    if answerable:
        return rec | scores | query_metrics(ranked, tuple(q["gold"]), tuple(r["recall_ks"]), r["k_eval"], r["k_eval"])
    return rec | {"abstained": scores["abstained"], "faithful": scores["faithful"]}


def metric_names(cfg: dict, answerable: bool) -> list[str]:
    if not answerable:
        return ["abstained", "faithful"]
    k = cfg["retrieve"]["k_eval"]
    return ([f"recall@{x}" for x in cfg["retrieve"]["recall_ks"]] + ["mrr", f"ndcg@{k}", f"paper_hit@{k}"]
            + ["faithful", "correct", "correct_if_answered", "abstained"])


def _token_stats(gens: list[dict]) -> dict:
    """Shows how close prompts came to num_ctx (truncation guard) and how long answers were."""
    prompt, output = [g["prompt_tokens"] for g in gens], [g["output_tokens"] for g in gens]
    return {"prompt_median": statistics.median(prompt), "prompt_max": max(prompt),
            "output_median": statistics.median(output), "output_max": max(output)}


def score(split: str, queries: list[dict], retrieved: dict, generated: dict, judged: dict, cfg: dict) -> dict:
    answerable = split not in ABSTENTION_SPLITS
    recs = [per_query_record(q, retrieved[q["query_id"]], generated[q["query_id"]], judged[q["query_id"]], cfg, answerable)
            for q in queries]
    verdicts = [v for r in recs for v in (r["faithfulness"], r["correctness"]) if v is not None]
    payload = {
        "split": split, "kind": "answerable" if answerable else "abstention", "n_queries": len(recs),
        "metrics": summarize(recs, metric_names(cfg, answerable)),
        "latency_ms_median": {"retrieve": statistics.median(r["retrieve_ms"] for r in recs),
                              "generate": statistics.median(r["generate_ms"] for r in recs)},
        "judge_calls": len(verdicts), "judge_errors": sum(v["verdict"] is None for v in verdicts),
        "generator_tokens": _token_stats([generated[q["query_id"]] for q in queries]),
    }
    if not answerable:
        # Answered *and* judged supported: another indexed paper may genuinely answer it (CLAUDE.md spot-check).
        payload["abstention_spot_check"] = [
            {k: r[k] for k in ("query_id", "query", "answer", "retrieved")} for r in recs if r["faithful"] == 1.0]
    return payload | {"per_query": recs}


def _fingerprint(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()


def prepare_run_dir(run_name: str, cfg: dict, fresh: bool) -> Path:
    run_dir = data_dir(cfg) / "runs" / run_name
    if fresh and run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = run_dir / "meta.json"
    if meta.exists() and json.loads(meta.read_text())["config_sha256"] != _fingerprint(cfg):
        raise SystemExit(f"{run_dir}: config changed since these checkpoints were written; rerun with --fresh")
    meta.write_text(json.dumps({"config_sha256": _fingerprint(cfg)}) + "\n")
    return run_dir


def run(split: str, run_name: str, stages: list[str], limit: int | None, fresh: bool, cfg: dict) -> None:
    queries = load_queries(split, cfg)[:limit]
    run_dir = prepare_run_dir(run_name, cfg, fresh)
    ret_path, gen_path, jud_path = run_dir / "retrieve.json", run_dir / "generate.jsonl", run_dir / "judge.jsonl"
    if "retrieve" in stages or not ret_path.exists():
        ret_path.write_text(json.dumps(retrieve_all(queries, cfg), ensure_ascii=False), encoding="utf-8")
        print(f"retrieve: {len(queries)} queries", flush=True)
    retrieved = json.loads(ret_path.read_text(encoding="utf-8"))
    if "generate" in stages:
        generate_all(queries, retrieved, gen_path, cfg)
    if "judge" in stages:
        judge_all(queries, retrieved, _read_jsonl(gen_path), jud_path, cfg, split not in ABSTENTION_SPLITS)
    if "score" in stages:
        payload = score(split, queries, retrieved, _read_jsonl(gen_path), _read_jsonl(jud_path), cfg)
        # Partial (--limit) runs stay out of the committed results/ directory.
        out_dir = run_dir if limit else RESULTS_DIR
        print(f"score: wrote {write_results(run_name, payload, cfg, out_dir)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--split", required=True)
    p.add_argument("--name", help="run name prefix (default: m3_<method>)")
    p.add_argument("--method", choices=METHODS, help="override [retrieve] method from the config")
    p.add_argument("--stages", default=",".join(STAGES))
    p.add_argument("--limit", type=int, help="first N queries only (smoke test; separate run directory)")
    p.add_argument("--fresh", action="store_true", help="discard this run's checkpoints first")
    a = p.parse_args()
    stages = a.stages.split(",")
    if unknown := set(stages) - set(STAGES):
        p.error(f"unknown stages {sorted(unknown)}; choose from {STAGES}")
    cfg = load_config()
    if a.method:
        cfg["retrieve"]["method"] = a.method  # lands in the config snapshot of the results file
    run_name = f"{a.name or 'm3_' + cfg['retrieve']['method']}_{a.split}" + (f"_limit{a.limit}" if a.limit else "")
    run(a.split, run_name, stages, a.limit, a.fresh, cfg)


if __name__ == "__main__":
    main()
