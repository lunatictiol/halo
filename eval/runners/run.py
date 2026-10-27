"""Run a pipeline on a split and score it: retrieve -> generate -> judge -> score.

    uv run python -m eval.runners.run --split dev_sample                     # method from config
    uv run python -m eval.runners.run --split dev_sample --pipeline graph     # M4 loop + M5 grounding check
    uv run python -m eval.runners.run --split dev_sample --pipeline graph --replay-from m4_graph_v2   # M5 eval
    uv run python -m eval.runners.run --split abstention_set --method dense --name m2_baseline
    uv run python -m eval.runners.run --split dev_sample --limit 5           # smoke test, separate run dir

With --pipeline graph, one `graph` stage (halo/graph/pipeline.py) replaces retrieve + generate. With
--replay-from, the graph stage reuses that run's retrieval and grading and reruns only generate + verify (D33).
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

from eval.judge import judge_correctness, judge_faithfulness, with_judge
from eval.metrics.abstention import is_abstention
from eval.metrics.answer import _score, answer_scores
from eval.metrics.citation import citation_scores, citation_totals
from eval.metrics.retrieval import query_metrics
from eval.metrics.slices import summarize
from eval.results import RESULTS_DIR, write_results
from halo.config import load_config
from halo.data import data_dir, load_hf, load_split
from halo.generate.baseline import answer
from halo.retrieve import METHODS, Retriever

STAGES = ("retrieve", "generate", "judge", "score")
GRAPH_STAGES = ("graph", "judge", "score")
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


def _graph_out(qid: str, out: dict, graph_ms: int) -> dict:
    from halo.graph.pipeline import abstained_by
    gen = out.get("generation") or {}
    return {"query_id": qid, "answer": out["answer"], "abstained": out["abstained"],
            "abstain_reason": out["abstain_reason"], "abstained_by": abstained_by(out),
            "retries": out["attempts"] - 1, "graph_ms": graph_ms,
            "hits": [{k: h[k] for k in HIT_KEYS} for h in out["hits"]],
            "generate_ms": gen.get("ms"), "prompt_tokens": gen.get("prompt_tokens"),
            "output_tokens": gen.get("output_tokens"), "raw_answer": out.get("raw_answer"),
            "grounding": out.get("grounding"), "trace": out["trace"]}


def graph_all(queries: list[dict], path: Path, cfg: dict) -> None:
    """Run the corrective loop per query; the record keeps the full node trace (queries, grades, reasons)."""
    from halo.graph.pipeline import build_graph, default_nodes
    todo = _pending(queries, _read_jsonl(path), "graph")
    if not todo:
        return
    retriever = Retriever(cfg)
    graph = build_graph(default_nodes(retriever, cfg), cfg["graph"]["max_retries"])
    try:
        for n, q in enumerate(todo, 1):
            start = time.perf_counter()
            out = graph.invoke({"question": q["query"]})
            _append_jsonl(path, _graph_out(q["query_id"], out, round((time.perf_counter() - start) * 1000)))
            if n % 10 == 0 or n == len(todo):
                print(f"  graph {n}/{len(todo)}", flush=True)
    finally:
        retriever.close()


def replay_all(queries: list[dict], source_path: Path, path: Path, cfg: dict) -> None:
    """Replay a graph run (D33): keep its retrieval, reranking, grading and rewrites, rerun generate + verify on
    the hits the grader approved. Grader abstentions are copied. The trace swaps in the new generate/verify
    entries, so graph_ms = the source's time without its generation + the new generate + verify time."""
    from halo.graph.pipeline import default_nodes, traced
    source = _read_jsonl(source_path)
    if missing := [q["query_id"] for q in queries if q["query_id"] not in source]:
        raise SystemExit(f"{source_path}: {len(missing)} queries missing, e.g. {missing[0]}")
    nodes = default_nodes(None, cfg)  # generate/verify never touch the retriever
    generate, verify = traced("generate", nodes["generate"]), traced("verify", nodes["verify"])
    todo = _pending(queries, _read_jsonl(path), "graph (replay)")
    for n, q in enumerate(todo, 1):
        src = source[q["query_id"]]
        trace = [t for t in src["trace"] if t["node"] != "generate"]
        state = {"question": q["query"], "hits": src["hits"], "attempts": src["retries"] + 1, "abstained": True,
                 "answer": src["answer"], "abstain_reason": src["abstain_reason"], "generation": None}
        if src["abstained_by"] != "grader":
            state |= (g := generate(state))
            state |= (v := verify(state))
            trace += g["trace"] + v["trace"]
        old_gen = sum(t["ms"] for t in src["trace"] if t["node"] == "generate")
        new = sum(t["ms"] for t in trace if t["node"] in ("generate", "verify"))
        _append_jsonl(path, _graph_out(q["query_id"], state | {"trace": trace}, src["graph_ms"] - old_gen + new))
        if n % 10 == 0 or n == len(todo):
            print(f"  replayed {n}/{len(todo)}", flush=True)


def graph_views(graphed: dict[str, dict]) -> dict[str, dict]:
    """The retrieve-stage shape judge_all and score consume. Retrieval metrics use the final attempt's hits
    (the context the answer was generated from); retrieve_ms sums retrieve + rerank over all attempts."""
    return {qid: {"hits": g["hits"],
                  "retrieve_ms": sum(t["ms"] for t in g["trace"] if t["node"] in ("retrieve", "rerank"))}
            for qid, g in graphed.items()}


def graph_record(rec: dict, g: dict, cfg: dict, answerable: bool) -> dict:
    """Loop-specific per-query fields; first_* retrieval metrics are on attempt 1 (= M3 without the loop)."""
    r = cfg["retrieve"]
    out = {"retries": g["retries"], "abstained_by": g["abstained_by"], "abstain_reason": g["abstain_reason"],
           "graph_ms": g["graph_ms"], "trace": g["trace"]}
    if answerable:
        first = [tuple(x) for x in next(t["top"] for t in g["trace"] if t["node"] == "rerank")]
        m = query_metrics(first, tuple(rec["gold"]), tuple(r["recall_ks"]), r["k_eval"], r["k_eval"])
        out |= {f"first_{k}": v for k, v in m.items()}
    return rec | out


def citation_record(rec: dict, g: dict, jud: dict) -> dict:
    """M5 fields. faithful_raw is the pre-check answer's faithfulness; it equals faithful when the check
    changed nothing (the same text was judged)."""
    gr = g.get("grounding")
    raw = None if not gr else (_score(_verdict(jud, "faithfulness_raw")) if "faithfulness_raw" in jud
                               else rec["faithful"])
    return rec | citation_scores(gr) | {"raw_answer": g.get("raw_answer"), "grounding": gr,
                                        "faithfulness_raw": jud.get("faithfulness_raw"), "faithful_raw": raw}


CITATION_METRICS = ["faithful_raw", "citation_validity", "citation_coverage", "citation_coverage_final",
                    "sentences_removed"]


def graph_summary(recs: list[dict], cfg: dict) -> dict:
    """Gate check: no query may exceed max_retries (counted from the trace, independently of the router)."""
    max_retries = cfg["graph"]["max_retries"]
    retrievals = [sum(t["node"] == "retrieve" for t in r["trace"]) for r in recs]
    return {"max_retries": max_retries, "retries_mean": round(statistics.mean(r["retries"] for r in recs), 4),
            "retries_histogram": {str(n): sum(r["retries"] == n for r in recs) for n in range(max_retries + 1)},
            "queries_over_retry_limit": sum(n > max_retries + 1 for n in retrievals),
            "abstained_by": {k: sum(r["abstained_by"] == k for r in recs) for k in ("grader", "generator", "grounding")},
            "graph_ms_median": statistics.median(r["graph_ms"] for r in recs)}


def judge_all(queries: list[dict], retrieved: dict, generated: dict, path: Path, cfg: dict, answerable: bool) -> None:
    """Faithfulness for every non-abstained answer; correctness only where a reference answer is valid."""
    k = cfg["retrieve"]["k_context"]
    todo = _pending(queries, _read_jsonl(path), "judge")
    for n, q in enumerate(todo, 1):
        gen, rec = generated[q["query_id"]], {"query_id": q["query_id"]}
        chunks = retrieved[q["query_id"]]["hits"][:k]
        if not gen["abstained"]:
            rec["faithfulness"] = judge_faithfulness(q["query"], gen["answer"], chunks, cfg)
            if answerable:
                rec["correctness"] = judge_correctness(q["query"], gen["answer"], q["reference"], cfg)
        # M5: also judge the pre-check answer when the grounding check changed it, to isolate the check's effect.
        if (gr := gen.get("grounding")) and gr["raw"] != gen["answer"]:
            rec["faithfulness_raw"] = judge_faithfulness(q["query"], gr["raw"], chunks, cfg)
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
    gens = [g for g in gens if g["prompt_tokens"] is not None]  # graph: grader abstentions never call the generator
    prompt, output = [g["prompt_tokens"] for g in gens], [g["output_tokens"] for g in gens]
    return {"prompt_median": statistics.median(prompt), "prompt_max": max(prompt),
            "output_median": statistics.median(output), "output_max": max(output)}


def score(split: str, queries: list[dict], retrieved: dict, generated: dict, judged: dict, cfg: dict,
          graphed: dict | None = None) -> dict:
    answerable = split not in ABSTENTION_SPLITS
    recs = [per_query_record(q, retrieved[q["query_id"]], generated[q["query_id"]], judged[q["query_id"]], cfg, answerable)
            for q in queries]
    names = metric_names(cfg, answerable)
    cited = graphed is not None and any("grounding" in g for g in graphed.values())
    if graphed is not None:
        recs = [graph_record(rec, graphed[rec["query_id"]], cfg, answerable) for rec in recs]
        names += ["retries"]
        if answerable:
            names += [f"first_recall@{k}" for k in cfg["retrieve"]["recall_ks"]] + ["first_mrr"]
    if cited:
        recs = [citation_record(rec, graphed[rec["query_id"]], judged[rec["query_id"]]) for rec in recs]
        names += CITATION_METRICS
    verdicts = [v for r in recs for v in (r["faithfulness"], r["correctness"], r.get("faithfulness_raw"))
                if v is not None]
    payload = {
        "split": split, "kind": "answerable" if answerable else "abstention", "n_queries": len(recs),
        "metrics": summarize(recs, names),
        "latency_ms_median": {"retrieve": statistics.median(r["retrieve_ms"] for r in recs),
                              "generate": statistics.median(r["generate_ms"] for r in recs if r["generate_ms"] is not None)},
        "judge_calls": len(verdicts), "judge_errors": sum(v["verdict"] is None for v in verdicts),
        "generator_tokens": _token_stats([generated[q["query_id"]] for q in queries]),
    }
    if not answerable:
        # Answered *and* judged supported: another indexed paper may genuinely answer it (CLAUDE.md spot-check).
        payload["abstention_spot_check"] = [
            {k: r[k] for k in ("query_id", "query", "answer", "retrieved")} for r in recs if r["faithful"] == 1.0]
    if graphed is not None:
        payload["graph"] = graph_summary(recs, cfg)
    if cited:
        payload["citations"] = citation_totals([r["grounding"] for r in recs])
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


def run(split: str, run_name: str, stages: list[str], limit: int | None, fresh: bool, cfg: dict,
        pipeline: str = "single", replay_from: str | None = None, rejudge_from: str | None = None) -> None:
    queries = load_queries(split, cfg)[:limit]
    run_dir = prepare_run_dir(run_name, cfg, fresh)
    ret_path, gen_path, jud_path = run_dir / "retrieve.json", run_dir / "generate.jsonl", run_dir / "judge.jsonl"
    graphed = None
    if pipeline == "graph":
        graph_path = run_dir / "graph.jsonl"
        if rejudge_from and not graph_path.exists():
            # M7: judge a finished run's saved answers again (e.g. with another judge); nothing is regenerated.
            shutil.copy(data_dir(cfg) / "runs" / f"{rejudge_from}_{split}" / "graph.jsonl", graph_path)
        if "graph" in stages and replay_from:
            replay_all(queries, data_dir(cfg) / "runs" / f"{replay_from}_{split}" / "graph.jsonl", graph_path, cfg)
        elif "graph" in stages:
            graph_all(queries, graph_path, cfg)
        graphed = _read_jsonl(graph_path)
        retrieved, generated = graph_views(graphed), graphed
    else:
        if "retrieve" in stages or not ret_path.exists():
            ret_path.write_text(json.dumps(retrieve_all(queries, cfg), ensure_ascii=False), encoding="utf-8")
            print(f"retrieve: {len(queries)} queries", flush=True)
        retrieved = json.loads(ret_path.read_text(encoding="utf-8"))
        if "generate" in stages:
            generate_all(queries, retrieved, gen_path, cfg)
        generated = _read_jsonl(gen_path)
    if "judge" in stages:
        judge_all(queries, retrieved, generated, jud_path, cfg, split not in ABSTENTION_SPLITS)
    if "score" in stages:
        payload = score(split, queries, retrieved, generated, _read_jsonl(jud_path), cfg, graphed)
        if replay_from:
            src = json.loads((RESULTS_DIR / f"{replay_from}_{split}.json").read_text(encoding="utf-8"))
            payload = {"replayed_from": {"run": src["run"], "git": src["git"]}} | payload
        # Partial (--limit) runs stay out of the committed results/ directory.
        out_dir = run_dir if limit else RESULTS_DIR
        print(f"score: wrote {write_results(run_name, payload, cfg, out_dir)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--split", required=True)
    p.add_argument("--name", help="run name prefix (default: m3_<method>, or m4_graph)")
    p.add_argument("--method", choices=METHODS, help="override [retrieve] method from the config")
    p.add_argument("--pipeline", choices=("single", "graph"), default="single",
                   help="single: one retrieval + one answer (M2/M3); graph: M4 corrective loop")
    p.add_argument("--replay-from", help="graph only: reuse this graph run's retrieval and grades, e.g. m4_graph_v2")
    p.add_argument("--stages", help=f"default: {','.join(STAGES)} (single) or {','.join(GRAPH_STAGES)} (graph)")
    p.add_argument("--limit", type=int, help="first N queries only (smoke test; separate run directory)")
    p.add_argument("--fresh", action="store_true", help="discard this run's checkpoints first")
    p.add_argument("--collection", help="override [retrieve] collection; M1-M5 runs used dev_slice (D36)")
    p.add_argument("--judge", help="use [judges.<name>] instead of the default [judge], e.g. gemini (M7)")
    p.add_argument("--rejudge-from", help="graph only: judge this graph run's saved answers again, e.g. m6_graph "
                                         "(implies --stages judge,score)")
    a = p.parse_args()
    allowed = GRAPH_STAGES if a.pipeline == "graph" else STAGES
    stages = a.stages.split(",") if a.stages else list(allowed)
    if unknown := set(stages) - set(allowed):
        p.error(f"unknown stages {sorted(unknown)}; choose from {allowed}")
    cfg = load_config()
    if a.method:
        cfg["retrieve"]["method"] = a.method  # lands in the config snapshot of the results file
    if a.collection:
        cfg["retrieve"]["collection"] = a.collection
    if (a.replay_from or a.rejudge_from) and a.pipeline != "graph":
        p.error("--replay-from and --rejudge-from need --pipeline graph")
    if a.rejudge_from:
        stages = ["judge", "score"]
    cfg = with_judge(cfg, a.judge)
    loop_name = "m5_cite" if a.replay_from else "m4_graph"
    default_name = loop_name if a.pipeline == "graph" else "m3_" + cfg["retrieve"]["method"]
    run_name = f"{a.name or default_name}_{a.split}" + (f"_limit{a.limit}" if a.limit else "")
    run(a.split, run_name, stages, a.limit, a.fresh, cfg, a.pipeline, a.replay_from, a.rejudge_from)


if __name__ == "__main__":
    main()
