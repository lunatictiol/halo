# M5 gate: citations and grounding check

Final configuration: `cite-v2` generator (P-labels, D31/D34) and `check-v2` grounding check (one joint check per sentence, uncited sentences checked, failed sentences re-attributed to a single supporting passage; D32/D35), on top of M4 `m4_graph_v2` (replayed, D33). Full report with examples and both review samples: [`m5_check_v2_report.md`](m5_check_v2_report.md). Superseded runs: [`m5_cite_v2_report.md`](m5_cite_v2_report.md) (check-v1), [`m5_report.md`](m5_report.md) (cite-v1).

- [x] **Citation validity and coverage measured on `dev_sample` and saved** (`m5_check_v2_dev_sample.json`): validity 0.976 (self-checked, D33), coverage 0.927 before the check and 1.000 after it (unsupported uncited sentences are removed), 1.0% of sentences removed. 511 citations: 501 supported, 10 unsupported, 0 out of range, 0 checker errors; 60 sentences (re-)attributed.
- [x] **Faithfulness after the grounding check vs M4:**

  | | M4 `m4_graph_v2` | M5 `m5_check_v2` |
  |---|---|---|
  | Faithful (`dev_sample`) | 0.986 | 0.986 (pre-check 0.980) |
  | Correct | 0.908 | 0.901 |
  | Correct when answered | 0.939 | 0.938 |
  | False-abstention rate | 0.033 | 0.040 |
  | Abstention rate on `abstention_set` | 0.882 | 0.862 |
  | Median end-to-end ms (`dev_sample`, stitched) | 16,214 | 26,732 |

  Faithfulness is unchanged vs M4. The whole-answer judge already rates nearly all answers faithful (D33), so it cannot show what the per-sentence check catches; the removed-sentence examples in the report do.
- [x] **10 cited answers shown for manual review:** new seeded sample (seed 6): 10/10 valid. The earlier cite-v2 sample re-reviewed under check-v2: 7/10, same 3 failures (D35). Known limitation: the qwen3:8b checker is lenient, so self-checked validity overstates real validity (17/20 reviewed answers valid).

Caveat: cite-v2 and check-v2 were both designed after reading failures on `dev_sample`, so these numbers are optimistic; `full` in M6 is the clean measurement.
