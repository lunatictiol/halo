# m3_hybrid_rerank: summary

Generator `qwen3:8b`, judge `qwen3:8b`, commit `ce575d3`. Source files: `results/m3_hybrid_rerank_dev_sample.json`, `results/m3_hybrid_rerank_abstention_set.json`.

## `dev_sample` (answerable)

| Slice | n | R@5 | R@10 | MRR | nDCG@10 | Paper@10 | Faithful | Correct | Correct|ans | False-abst |
|---|---|---|---|---|---|---|---|---|---|---|
| **overall** | 303 | 0.944 | 0.970 | 0.830 | 0.865 | 1.000 | 0.987 | 0.908 | 0.926 | 0.020 |
| type: abstractive | 179 | 0.922 | 0.961 | 0.800 | 0.840 | 1.000 | 1.000 | 0.911 | 0.921 | 0.011 |
| type: extractive | 124 | 0.976 | 0.984 | 0.873 | 0.900 | 1.000 | 0.967 | 0.903 | 0.933 | 0.032 |
| modality: text | 204 | 0.961 | 0.980 | 0.857 | 0.888 | 1.000 | 0.985 | 0.951 | 0.960 | 0.010 |
| modality: text-image | 72 | 0.903 | 0.931 | 0.760 | 0.803 | 1.000 | 1.000 | 0.806 | 0.853 | 0.056 |
| modality: text-table | 13 | 0.923 | 1.000 | 0.832 | 0.871 | 1.000 | 0.923 | 0.769 | 0.769 | 0.000 |
| modality: text-table-image | 14 | 0.929 | 1.000 | 0.784 | 0.838 | 1.000 | 1.000 | 0.929 | 0.929 | 0.000 |

False-abst = share of answerable questions the model refused. Correct counts a refusal as wrong; Correct|ans is over answered questions only. Faithful is over answered questions only.

Median latency per query: retrieve 847 ms, generate 13704 ms. Judge errors: 0/594.

## Abstention

- Abstention rate on `abstention_set`: **0.809** (n=152)
- Answered abstention questions judged *supported* by retrieved context (spot-check candidates): 23
