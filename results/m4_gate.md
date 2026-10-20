# M4 gate: corrective loop and abstention

Final configuration: `grade-v2` grader (D30), `rewrite-v1` rewriter, `max_retries = 2`, hybrid RRF → bge rerank, qwen3:8b with `num_gpu = 22` (D29). Full report with examples: [`m4_graph_v2_report.md`](m4_graph_v2_report.md). The superseded `grade-v1` run: [`m4_report.md`](m4_report.md).

- [x] **Graph diagram generated from the graph definition:** [`docs/m4_graph.md`](../docs/m4_graph.md) (`scripts/draw_graph.py`, Mermaid from `build_graph`).
- [x] **No query exceeds the retry limit:** `queries_over_retry_limit = 0` on `dev_sample` (303) and `abstention_set` (152), recounted from each query's node trace (`graph` block of `m4_graph_v2_*.json`). Retries histogram: dev {0: 287, 1: 6, 2: 10}, abstention {0: 17, 1: 6, 2: 129}.
- [x] **Comparison vs M3:**

  | | M3 `m3_hybrid_rerank` | M4 `m4_graph_v2` |
  |---|---|---|
  | Correct (`dev_sample`) | 0.908 | 0.908 |
  | Correct when answered | 0.926 | 0.939 |
  | Faithful | 0.987 | 0.986 |
  | False-abstention rate | 0.020 | 0.033 |
  | Abstention rate on `abstention_set` | 0.809 | **0.882** |
  | Avg retries / query (dev / abstention) | 0 | 0.086 / 1.737 |
  | Median end-to-end ms (`dev_sample`) | 14,551 | 16,214 |

- [x] **5 rescued first retrievals and 5 correct abstentions** saved in `m4_graph_v2_report.md` (7 rescues in total).

Caveat: `grade-v2` was written after reading `grade-v1` failures on `dev_sample`, so these dev numbers are optimistic for the grader; `full` in M6 is the clean measurement.
