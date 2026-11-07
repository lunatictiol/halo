# M9 gate: contextual enrichment and chunking benchmark

Design and decisions: DECISIONS.md D41 (fixed-size baseline), D42 (contextual enrichment). Benchmark: `eval/runners/chunking.py` → [`m9_chunking.md`](m9_chunking.md). Ingestion: `scripts/ingest.py --strategy section|fixed|ctx`. Enrichment: `halo/ingest/enrich.py`, `[enrich]` in `config/default.toml`, model pilot [`m9_enrich_pilot.json`](m9_enrich_pilot.json).

- [x] **Table and chart in README: R@5, R@10, MRR, nDCG@10 per strategy on `dev_sample`, plus ingest time and enrichment cost.** README "Chunking benchmark (M9)"; full table, slices and charts in [`m9_chunking.md`](m9_chunking.md).

  | Strategy (hybrid_rerank) | Chunks | R@5 | R@10 | MRR | nDCG@10 | Ingest | Enrichment |
  |---|---|---|---|---|---|---|---|
  | section-aware | 6,740 | 0.944 | 0.970 | 0.830 | 0.865 | 3 min | none |
  | fixed-size | 5,406 | 0.766 | 0.815 | 0.642 | 0.684 | 2 min | none |
  | section-aware + context | 6,740 | 0.941 | 0.980 | 0.837 | 0.872 | 188 min | 6,453 gemma3 calls, 5.17 M in / 0.41 M out tokens, 3.2 GPU-h |

  Sources: `m9_retrieval_<strategy>_<method>_dev_sample.json`, `m9_ingest_dev_slice*.json`. Optional parent–child strategy: not built.
- [x] **End-to-end Correct / Faithful / abstention for the chosen strategy vs M6 on `dev_sample` and `abstention_set`.** The chosen strategy is the shipped section-aware chunker, unchanged, so its end-to-end numbers are the existing runs on the same index: [`m5_check_v2_dev_sample.json`](m5_check_v2_dev_sample.json) (Correct 0.901, Faithful 0.986) and [`m5_check_v2_abstention_set.json`](m5_check_v2_abstention_set.json) (abstention 0.862); on the full index, `m6_graph_*`. The enriched collection was **not** run end-to-end: retrieval is tied (36 questions better, 35 worse), and 216 of 427 M6 wrong answers already had the gold section in the top-5 (D38, D42).
- [x] **Adoption.** Not adopted (D42): no measurable retrieval gain over section-aware at ~60× the ingest cost (about 29 GPU-hours for the full index). The full index is not rebuilt and the `full` split is not re-run.

Other checks: the section-aware `dev_slice` re-ingested to the same 6,740 chunks, and its hybrid_rerank metrics reproduce M3 exactly (`m3_ablation.md`). The CI gate file `ci_retrieval_dev_sample.json` was re-run at the final M9 code commit. `uv run pytest`: 103 passed (6 new). `uv run ruff check .`: clean.
