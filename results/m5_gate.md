# M5 gate: citations and grounding check

Final configuration: `cite-v2` generator (P-labels, D31/D34) and `check-v1` per-(sentence, passage) grounding check with re-attribution (D32/D34), on top of M4 `m4_graph_v2` (replayed, D33). Full report with examples and the review sample: [`m5_cite_v2_report.md`](m5_cite_v2_report.md). Superseded `cite-v1` run: [`m5_report.md`](m5_report.md).

- [x] **Citation validity and coverage measured on `dev_sample` and saved** (`m5_cite_v2_dev_sample.json`): validity 0.971 (self-checked, D33), coverage 0.927 pre-check / 0.929 final, 0.5% of sentences removed. 510 citations: 497 supported, 13 unsupported, 0 out of range, 0 checker errors; 6 sentences re-attributed.
- [x] **Faithfulness after the check vs M4:**

  | | M4 `m4_graph_v2` | M5 `m5_cite_v2` |
  |---|---|---|
  | Faithful (`dev_sample`) | 0.986 | 0.980 (pre-check 0.976) |
  | Correct | 0.908 | 0.894 |
  | Correct when answered | 0.939 | 0.928 |
  | False-abstention rate | 0.033 | 0.036 |
  | Abstention rate on `abstention_set` | 0.882 | 0.868 |
  | Median end-to-end ms (`dev_sample`, stitched) | 16,214 | 24,922 |

  Faithfulness is flat: the whole-answer judge already rates nearly all answers faithful, including the check-changed answers before the check (D33), so it cannot show the check's effect. The check's value shows in the removed-sentence examples in the report.
- [ ] **10 cited answers for manual review:** in `m5_cite_v2_report.md` (seeded sample, each citation with its passage excerpt). Agreement rate goes into DECISIONS.md after review.
