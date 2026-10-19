# M3 gate — hybrid retrieval and reranking

Branch `m3`. Retrieval ablation at commit `ce575d3` (dense, bm25, hybrid, hybrid_rerank) and the next commit
(bm25_rerank row); answer runs at `ce575d3`. Every results file records `dirty: false`.

## 1. Ablation table on `dev_sample` with retrieval metrics and latency per query — [OK]

`results/m3_ablation.md` (sources: `results/m3_retrieval_{dense,bm25,hybrid,hybrid_rerank,bm25_rerank}_dev_sample.json`).

| Method | R@5 | R@10 | MRR | nDCG@10 | R@50 | median ms | p95 ms |
|---|---|---|---|---|---|---|---|
| dense | 0.868 | 0.927 | 0.707 | 0.761 | 0.980 | 53 | 75 |
| bm25 | 0.924 | 0.960 | 0.758 | 0.808 | 0.990 | 0 | 0 |
| hybrid | 0.908 | 0.967 | 0.759 | 0.810 | 0.990 | 53 | 77 |
| hybrid_rerank | 0.944 | 0.970 | 0.830 | 0.865 | 0.990 | 849 | 873 |
| bm25_rerank | 0.941 | 0.967 | 0.827 | 0.862 | 0.990 | 836 | 949 |

## 2. Chosen configuration and reason recorded in DECISIONS.md with the numbers — [OK]

`hybrid_rerank`. See DECISIONS.md D21–D25.

## 3. Honest report where hybrid or rerank does not improve — [OK, investigated]

- Hybrid improves on dense on every metric, but **not on BM25 alone** for R@5 (0.908 vs 0.924); MRR is equal.
  Cause: 13 questions are top-5 for BM25 only and are lost in equal-weight RRF; fusion regains 8 dense-only hits (D22).
- Follow-up: `bm25_rerank` was added to test whether dense still matters after reranking. Result: a tie with
  hybrid_rerank (1 query better, 1 worse, paired gold ranks). Dense is kept as a hypothesis, not a measured gain (D24).
- Reranking improves on every method and every slice.

## 4. Determinism — [OK]

hybrid_rerank gold ranks are identical for 303/303 queries between `results/m3_retrieval_hybrid_rerank_dev_sample.json`
(ablation) and `results/m3_hybrid_rerank_dev_sample.json` (separate process, answer run). The dense row reproduces M2's
retrieval metrics exactly (`results/m2_baseline_dev_sample.json`).

## 5. Answer metrics for the chosen config (baseline for M4) — [OK, with one regression]

`results/m3_hybrid_rerank_summary.md` vs `results/m2_baseline_summary.md`:

| | M2 baseline | M3 hybrid_rerank |
|---|---|---|
| Correct (dev_sample) | 0.848 | 0.908 |
| False-abstention | 0.063 | 0.020 |
| Faithful | 0.975 | 0.987 |
| Abstention rate (abstention_set) | 0.875 | **0.809** (regression) |

The abstention regression is explained in D24 and is the target of M4's grader.

## 6. Unit tests — [OK]

`uv run pytest`: 39 passed (new: `tests/test_fusion.py`, `tests/test_bm25.py`).
