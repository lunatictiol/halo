# M3 retrieval ablation on `dev_sample`

n = 303 queries. Commit `ce575d3`. Reranker `BAAI/bge-reranker-v2-m3`, RRF k = 60, 50 candidates per retriever. Source files: `results/m3_retrieval_dense_dev_sample.json`, `results/m3_retrieval_bm25_dev_sample.json`, `results/m3_retrieval_hybrid_dev_sample.json`, `results/m3_retrieval_hybrid_rerank_dev_sample.json`, `results/m3_retrieval_bm25_rerank_dev_sample.json`.

## Overall

| Method | R@5 | R@10 | MRR | nDCG@10 | Paper@10 | R@50 (ceiling) | Latency median (ms) | Latency p95 (ms) | Gold rank vs dense |
|---|---|---|---|---|---|---|---|---|---|
| dense | 0.868 | 0.927 | 0.707 | 0.761 | 0.993 | 0.980 | 53 | 75.0 | – |
| bm25 | 0.924 | 0.960 | 0.758 | 0.808 | 1.000 | 0.990 | 0 | 0.0 | 81 better / 59 worse / 163 same |
| hybrid | 0.908 | 0.967 | 0.759 | 0.810 | 1.000 | 0.990 | 53 | 77.0 | 78 better / 31 worse / 194 same |
| hybrid_rerank | 0.944 | 0.970 | 0.830 | 0.865 | 1.000 | 0.990 | 849 | 872.9 | 89 better / 33 worse / 181 same |
| bm25_rerank | 0.941 | 0.967 | 0.827 | 0.862 | 1.000 | 0.990 | 836 | 949.0 | 89 better / 34 worse / 180 same |

R@50: gold section anywhere in the candidate list, the most a reranker over that list could reach. Gold rank vs dense: queries whose first gold chunk moved up / down in the top-10.

## Latency by stage (median / p95 ms per query)

| Method | dense | bm25 | fuse | rerank |
|---|---|---|---|---|
| dense | 52.5 / 75.1 | – | – | – |
| bm25 | – | 0.2 / 0.4 | – | – |
| hybrid | 52.1 / 76.5 | 0.4 / 0.6 | 0.1 / 0.1 | – |
| hybrid_rerank | 43.0 / 56.5 | 0.5 / 0.6 | 0.1 / 0.1 | 807.2 / 826.1 |
| bm25_rerank | – | 0.6 / 0.9 | – | 835.6 / 948.4 |

## By question type (R@5 / MRR)

| Method | abstractive (n=179) | extractive (n=124) |
|---|---|---|
| dense | 0.838 / 0.654 | 0.911 / 0.784 |
| bm25 | 0.911 / 0.737 | 0.944 / 0.788 |
| hybrid | 0.894 / 0.728 | 0.927 / 0.803 |
| hybrid_rerank | 0.922 / 0.800 | 0.976 / 0.873 |
| bm25_rerank | 0.922 / 0.800 | 0.968 / 0.865 |

## By modality (R@5 / MRR)

| Method | text (n=204) | text-image (n=72) | text-table (n=13) | text-table-image (n=14) |
|---|---|---|---|---|
| dense | 0.892 / 0.730 | 0.792 / 0.660 | 0.923 / 0.782 | 0.857 / 0.546 |
| bm25 | 0.946 / 0.785 | 0.847 / 0.705 | 1.000 / 0.730 | 0.929 / 0.665 |
| hybrid | 0.926 / 0.787 | 0.875 / 0.705 | 0.923 / 0.816 | 0.786 / 0.576 |
| hybrid_rerank | 0.961 / 0.857 | 0.903 / 0.760 | 0.923 / 0.832 | 0.929 / 0.784 |
| bm25_rerank | 0.956 / 0.852 | 0.903 / 0.762 | 0.923 / 0.832 | 0.929 / 0.784 |
