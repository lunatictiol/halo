# M7 judge calibration

Generated from [`m7_judge_calibration.json`](m7_judge_calibration.json) by `eval.runners.calibrate report`. 25 faithfulness and 25 correctness items, labeled blind; negatives oversampled by the qwen verdict (D39), so agreement here is not the population agreement.

| Kind | Judge | Model | n | Agreement | Cohen's κ |
|---|---|---|---|---|---|
| faithfulness | qwen | `qwen3:8b` | 25 | 0.76 | 0.4828 |
| faithfulness | llama | `llama3.1:8b` | 25 | 0.64 | 0.1176 |
| correctness | qwen | `qwen3:8b` | 25 | 0.8 | 0.5614 |
| correctness | llama | `llama3.1:8b` | 25 | 0.8 | 0.4813 |

Judge vs judge and human negatives:

- **faithfulness:** qwen vs llama κ 0.1627; 10 of 25 labeled negative by me.
- **correctness:** qwen vs llama κ 0.6429; 7 of 25 labeled negative by me.

## Confusion (judge verdict → my label)

**faithfulness**

| Judge | supported->supported | supported->unsupported | unsupported->supported | unsupported->unsupported |
|---|---|---|---|---|
| qwen | 13 | 4 | 2 | 6 |
| llama | 15 | 9 | 0 | 1 |

**correctness**

| Judge | correct->correct | correct->incorrect | incorrect->correct | incorrect->incorrect |
|---|---|---|---|---|
| qwen | 14 | 1 | 4 | 6 |
| llama | 16 | 3 | 2 | 4 |
