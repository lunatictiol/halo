"""Measure local LLM generation speed (tokens/sec) via the Ollama API; save to results/.

    uv run python scripts/bench_llm.py
"""

import json
import statistics
import subprocess
import urllib.request
from datetime import datetime, timezone

from halo.config import ROOT, load_config

PROMPT = ("Explain in about 200 words how hybrid retrieval with BM25 and dense embeddings "
          "is combined using reciprocal rank fusion.")
RUNS = 3
MAX_TOKENS = 256


def generate(url: str, model: str) -> dict:
    body = json.dumps({"model": model, "prompt": PROMPT, "stream": False, "think": False,
                       "options": {"num_predict": MAX_TOKENS, "temperature": 0}}).encode()
    req = urllib.request.Request(f"{url}/api/generate", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def main() -> None:
    m = load_config()["models"]
    generate(m["ollama_url"], m["llm"])  # warm-up: loads weights into VRAM, not timed
    runs = []
    for _ in range(RUNS):
        r = generate(m["ollama_url"], m["llm"])
        runs.append({"eval_tokens": r["eval_count"],
                     "gen_tokens_per_sec": r["eval_count"] / (r["eval_duration"] / 1e9),
                     "prompt_tokens_per_sec": r["prompt_eval_count"] / (r["prompt_eval_duration"] / 1e9)})
    ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True, cwd=ROOT).stdout.strip()
    result = {
        "kind": "llm_bench", "model": m["llm"], "gpu": gpu, "git_commit": commit,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runs": runs,
        "median_gen_tokens_per_sec": round(statistics.median(r["gen_tokens_per_sec"] for r in runs), 1),
        "ollama_ps": ps.strip(),
    }
    out = ROOT / "results" / "m0_llm_bench.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{m['llm']} on {gpu}: median {result['median_gen_tokens_per_sec']} tok/s -> {out}")
    print(ps)


if __name__ == "__main__":
    main()
