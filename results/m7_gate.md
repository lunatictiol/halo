# M7 gate: judge calibration

Calibration: [`m7_judge_calibration.md`](m7_judge_calibration.md) ([`.json`](m7_judge_calibration.json)). Design and decision: DECISIONS.md D39 (D18, D20 updated). Sample, blind sheet, labels and per-judge verdicts: `eval/calibration/`.

- [x] **κ for both judges against my labels saved** to [`m7_judge_calibration.md`](m7_judge_calibration.md). 50 items (25 faithfulness, 25 correctness) drawn with a fixed seed (20261023) from the M6 headline runs, negatives oversampled, labeled blind:

  | Kind | qwen3:8b agreement / κ | llama3.1:8b agreement / κ |
  |---|---|---|
  | faithfulness | 0.76 / 0.48 | 0.64 / 0.12 |
  | correctness | 0.80 / 0.56 | 0.80 / 0.48 |

  The planned second judge, Gemini 2.5 Flash, was dropped (free tier is 20 requests/day), as was hosted Gemma 4 31B (persistent 500/503 errors). llama3.1:8b, from another model family and run locally, replaced them (D39).
- [x] **Chosen judge and reason recorded** (D39): qwen3:8b stays, because it has the higher κ on both kinds. llama3.1:8b said "supported" on 24 of 25 faithfulness items. D18 now records the measured κ and the direction of the bias. D20's "not done yet" status is closed by D39.
- [x] **README results regenerated with the chosen judge; numbers that moved are called out.** None moved. The chosen judge is the M6 judge, and re-judging is deterministic: 50 of 50 qwen verdicts on the calibration sample match the saved M6 verdicts ([`eval/calibration/m7_verdicts_qwen.jsonl`](../eval/calibration/m7_verdicts_qwen.jsonl)). So the full re-score of `m6_graph_{dev_sample,abstention_set,full}` (~6,600 judge calls) was not run; it would reproduce the same files. `eval.report.readme` regenerated the tables with no diff. The README limitation now states the measured κ and the direction of the error: Faithful is overstated (4 of 17 sampled "supported" were unsupported to me) and Correct somewhat understated (4 of 10 sampled "incorrect" were correct to me).
- [x] **Citation-validity gap stated in README limitations:** self-check 0.97+ vs 7 of 10 valid by manual review (D35).

Other checks: `uv run pytest`: 88 passed. The eval runner gained `--judge` and `--rejudge-from` (re-judge a saved graph run with any named judge, no regeneration), ready for a stricter `judge-v2` or a paid hosted judge.
