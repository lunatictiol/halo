"""M9 enrichment pilot: the same seeded sample of dev_slice chunks through each candidate model, timing and output
saved for review before the full enrichment run (D42). No cache: every call is measured.

    uv run python scripts/enrich_pilot.py --models qwen3:8b,gemma3 --n 50
"""

import argparse
import copy
import random
import statistics

from eval.results import write_results
from halo.config import load_config
from halo.data import load_corpus_doc
from halo.ingest.enrich import situate
from halo.ingest.index import all_payloads, open_index


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--models", default="qwen3:8b,gemma3")
    p.add_argument("--n", type=int, default=50)
    a = p.parse_args()
    cfg = load_config()
    client = open_index(cfg)
    chunks = sorted(all_payloads(client, "dev_slice"), key=lambda c: (c["paper_id"], c["chunk_idx"]))
    client.close()
    # Sample sorted by paper so consecutive calls share the title+abstract prompt prefix, as in a real ingest run.
    sample = sorted(random.Random(cfg["splits"]["seed"]).sample(chunks, a.n), key=lambda c: (c["paper_id"], c["chunk_idx"]))
    docs = {pid: load_corpus_doc(pid, cfg) for pid in {c["paper_id"] for c in sample}}
    out = {}
    for model in a.models.split(","):
        mcfg = copy.deepcopy(cfg)
        mcfg["enrich"]["model"] = model
        situate(sample[0], docs[sample[0]["paper_id"]], mcfg)  # warm-up: model load time is not per-chunk cost
        recs = []
        for c in sample:
            r = situate(c, docs[c["paper_id"]], mcfg)
            recs.append({"paper_id": c["paper_id"], "chunk_idx": c["chunk_idx"], "context": r["content"],
                         "prompt_tokens": r["prompt_tokens"], "output_tokens": r["output_tokens"], "ms": r["ms"]})
        ms = [r["ms"] for r in recs]
        out[model] = {"median_ms": statistics.median(ms), "mean_ms": round(statistics.mean(ms)),
                      "mean_output_tokens": round(statistics.mean(r["output_tokens"] for r in recs), 1),
                      "per_chunk": recs}
        print(f"{model}: median {out[model]['median_ms']} ms/chunk, mean {out[model]['mean_ms']} ms", flush=True)
    path = write_results("m9_enrich_pilot", {"kind": "enrich_pilot", "n_chunks": a.n,
                                             "sample": [{"paper_id": c["paper_id"], "chunk_idx": c["chunk_idx"],
                                                         "text": c["text"]} for c in sample],
                                             "models": out}, cfg)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
