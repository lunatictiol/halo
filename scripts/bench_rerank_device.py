"""Where should the reranker run when it alternates with qwen3:8b on one 6 GB GPU? (DECISIONS.md D29)

The M4 loop calls rerank -> LLM -> (rerank -> LLM)* per query, so the M3 trick of releasing the reranker
before a separate generation stage no longer applies. Each scenario runs in a fresh subprocess with Ollama's
model unloaded first, then alternates the real calls (embed -> rerank -> LLM) on dev_sample queries:

    gpu_rerank_first  reranker takes VRAM first; Ollama sizes its GPU layers to what is left
    ..._ngpuN         same, with the LLM capped at N GPU layers so nothing spills into shared memory
    gpu_llm_first     Ollama loads first; the reranker allocates afterwards (may spill to shared memory)
    cpu               reranker on CPU (fp32); Ollama keeps the GPU

    uv run python scripts/bench_rerank_device.py            # all scenarios -> results/m4_rerank_device_bench.json

per_attempt_ms_estimate = retrieve + rerank + 2 x LLM call (one grade + one rewrite or generate per attempt).
"""

import json
import statistics
import subprocess
import sys
import time
import urllib.request

from eval.results import RESULTS_DIR, git_state
from halo.config import load_config
from halo.data import load_hf, load_split

# (name, Ollama GPU layers for the LLM; None = Ollama's automatic choice). qwen3:8b has 36 layers.
SCENARIOS = (("gpu_rerank_first", None), ("gpu_llm_first", None), ("cpu", None),
             ("gpu_rerank_first", 22), ("gpu_rerank_first", 18), ("gpu_rerank_first", 14))
N_QUERIES, WARMUP = 10, 2


def _ollama(path: str, body: dict | None, cfg: dict) -> dict:
    req = urllib.request.Request(f"{cfg['models']['ollama_url']}{path}", json.dumps(body).encode() if body else None,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def _processor_split(cfg: dict) -> str:
    """Ollama's CPU/GPU share for the LLM, computed the way `ollama ps` prints it."""
    for m in _ollama("/api/ps", None, cfg)["models"]:
        if m["name"].startswith(cfg["models"]["llm"]):
            gpu = m["size_vram"] / m["size"]
            return f"{round((1 - gpu) * 100)}%/{round(gpu * 100)}% CPU/GPU"
    return "not loaded"


def scenario(name: str, num_gpu: int | None) -> dict:
    from halo.generate.baseline import answer
    from halo.retrieve import Retriever
    from halo.retrieve.rerank import rerank

    cfg = load_config()
    cfg["rerank"]["device"] = "cpu" if name == "cpu" else "cuda"
    if num_gpu is not None:
        cfg["llm"]["num_gpu"] = num_gpu
    queries = load_hf("queries.json", cfg)
    qids = load_split("dev_sample")["query_ids"][:N_QUERIES + WARMUP]
    _ollama("/api/generate", {"model": cfg["models"]["llm"], "keep_alive": 0}, cfg)  # unload: clean VRAM

    retriever = Retriever(cfg)
    retriever.bm25  # build the BM25 index outside the timed loop
    if name == "gpu_llm_first":
        answer("warm-up", [], cfg)
    else:
        rerank("warm-up", [{"text": "warm-up"}], cfg)

    # Embedding (nomic-embed-text, also served by Ollama) runs inside the loop, as in the graph.
    rows = []
    for q in qids:
        start = time.perf_counter()
        candidates, _ = retriever.retrieve(queries[q]["query"], "hybrid")
        mid = time.perf_counter()
        hits = rerank(queries[q]["query"], candidates, cfg)
        end = time.perf_counter()
        resp = answer(queries[q]["query"], hits[:cfg["retrieve"]["k_context"]], cfg)
        rows.append({"query_id": q, "retrieve_ms": round((mid - start) * 1000), "rerank_ms": round((end - mid) * 1000),
                     "llm_ms": resp["ms"], "output_tokens": resp["output_tokens"],
                     "top5": [[h["paper_id"], h["chunk_idx"]] for h in hits[:5]]})
    retriever.close()
    timed = rows[WARMUP:]
    return {"scenario": name if num_gpu is None else f"{name}_ngpu{num_gpu}", "llm_num_gpu": num_gpu,
            "ollama_processor": _processor_split(cfg),
            "retrieve_ms_median": statistics.median(r["retrieve_ms"] for r in timed),
            "rerank_ms_median": statistics.median(r["rerank_ms"] for r in timed),
            "llm_ms_median": statistics.median(r["llm_ms"] for r in timed),
            "llm_ms_per_output_token_median": statistics.median(r["llm_ms"] / max(r["output_tokens"], 1) for r in timed),
            "rows": rows}


def main() -> None:
    if len(sys.argv) == 3:  # child process: one scenario, JSON on the last stdout line
        print(json.dumps(scenario(sys.argv[1], None if sys.argv[2] == "auto" else int(sys.argv[2]))))
        return
    out = []
    for name, num_gpu in SCENARIOS:
        print(f"running {name} num_gpu={num_gpu or 'auto'}", flush=True)
        proc = subprocess.run([sys.executable, __file__, name, str(num_gpu or "auto")], capture_output=True, text=True,
                              check=True)
        res = json.loads(proc.stdout.strip().splitlines()[-1])
        print(f"  {res['ollama_processor']}: retrieve {res['retrieve_ms_median']} ms, rerank {res['rerank_ms_median']} ms, LLM {res['llm_ms_median']} ms", flush=True)
        res["per_attempt_ms_estimate"] = res["retrieve_ms_median"] + res["rerank_ms_median"] + 2 * res["llm_ms_median"]
        out.append(res)
    ref = {r["query_id"]: r["top5"] for r in out[0]["rows"]}
    for res in out:  # fp16 GPU vs fp32 CPU can reorder near-ties; report how much
        res["top5_identical_to_gpu"] = sum(r["top5"] == ref[r["query_id"]] for r in res["rows"])
    path = RESULTS_DIR / "m4_rerank_device_bench.json"
    path.write_text(json.dumps({"kind": "rerank_device_bench", "git": git_state(), "n_queries": N_QUERIES,
                                "warmup": WARMUP, "scenarios": out}, indent=2) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
