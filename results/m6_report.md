# M6 report: dev index vs full index

Runs: `m5_check_v2_*` (100-paper dev index), `m6_graph_*` (980-paper full index). Same pipeline, generator and judge (`qwen3:8b`).

## Same run, same index: dev_sample questions vs the rest of `full`

| Slice | dev_sample questions | other questions |
|---|---|---|
| recall@5 | 0.927 (n=303) | 0.915 (n=2590) |
| mrr | 0.806 (n=303) | 0.802 (n=2590) |
| correct | 0.894 (n=303) | 0.835 (n=2588) |
| correct_if_answered | 0.934 (n=290) | 0.892 (n=2424) |
| abstained | 0.043 (n=303) | 0.063 (n=2590) |
| faithful | 0.986 (n=290) | 0.979 (n=2424) |
| correct, text | 0.931 (n=204) | 0.904 (n=1597) |
| correct, text-image | 0.806 (n=72) | 0.699 (n=664) |
| correct, text-table | 0.769 (n=13) | 0.769 (n=130) |
| correct, text-table-image | 0.929 (n=14) | 0.782 (n=197) |
| correct, gold in top-5 | 0.915 (n=281) | 0.859 (n=2369) |
| correct, gold not in top-5 | 0.636 (n=22) | 0.571 (n=219) |

Wrong answers among the other questions (427): answered, gold in top-5 216, abstained 164, answered, gold not in top-5 47.

## Abstention: same 152 questions, dev index vs full index

- Answered instead of abstaining: dev index 21, full index 34 (16 answered on both).
- Paper of the top-ranked passage for the full-index answers: official distractor 17, other source paper 10, dev_slice paper 7.
- First grade for those answers: sufficient 24, insufficient 10.
