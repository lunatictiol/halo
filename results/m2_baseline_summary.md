# m2_baseline: summary

Generator `qwen3:8b`, judge `qwen3:8b`, commit `22ff93e`. Source files: `results/m2_baseline_dev_sample.json`, `results/m2_baseline_abstention_set.json`.

## `dev_sample` (answerable)

| Slice | n | R@5 | R@10 | MRR | nDCG@10 | Paper@10 | Faithful | Correct | Correct|ans | False-abst |
|---|---|---|---|---|---|---|---|---|---|---|
| **overall** | 303 | 0.868 | 0.927 | 0.707 | 0.761 | 0.993 | 0.975 | 0.848 | 0.905 | 0.063 |
| type: abstractive | 179 | 0.838 | 0.927 | 0.654 | 0.721 | 0.994 | 1.000 | 0.866 | 0.901 | 0.039 |
| type: extractive | 124 | 0.911 | 0.927 | 0.784 | 0.819 | 0.992 | 0.938 | 0.823 | 0.911 | 0.097 |
| modality: text | 204 | 0.892 | 0.931 | 0.730 | 0.780 | 0.990 | 0.969 | 0.868 | 0.922 | 0.059 |
| modality: text-image | 72 | 0.792 | 0.903 | 0.660 | 0.719 | 1.000 | 1.000 | 0.778 | 0.862 | 0.097 |
| modality: text-table | 13 | 0.923 | 0.923 | 0.782 | 0.818 | 1.000 | 0.923 | 0.923 | 0.923 | 0.000 |
| modality: text-table-image | 14 | 0.857 | 1.000 | 0.546 | 0.654 | 1.000 | 1.000 | 0.857 | 0.857 | 0.000 |

False-abst = share of answerable questions the model refused. Correct counts a refusal as wrong; Correct|ans is over answered questions only. Faithful is over answered questions only.

Median latency per query: retrieve 2184 ms, generate 9226 ms. Judge errors: 0/568.

## Abstention

- Abstention rate on `abstention_set`: **0.875** (n=152)
- Answered abstention questions judged *supported* by retrieved context (spot-check candidates): 14
