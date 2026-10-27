# M8 gate: CI regression gate

Design and decision: DECISIONS.md D40. Gate: `eval/runners/ci.py` (`run` locally, `check` in CI), thresholds in `config/default.toml [ci]`, workflow `.github/workflows/ci.yml` (lint → pytest → gate). Baseline: [`m8_ci_baseline.json`](m8_ci_baseline.json); checked file: [`ci_retrieval_dev_sample.json`](ci_retrieval_dev_sample.json).

- [x] **A PR with a deliberately degraded config fails the gate; a clean PR passes.**

  | PR | Change | CI run | Gate result |
  |---|---|---|---|
  | [#10](https://github.com/lunatictiol/halo/pull/10) (m8 → main) | none | [40514815501](https://github.com/lunatictiol/halo/actions/runs/40514815501) | **passed**: R@5 0.9373, MRR 0.8154, delta +0.0000 |
  | [#11](https://github.com/lunatictiol/halo/pull/11), push 1 | `method = "hybrid"` (rerank off), gate not re-run | [40516277310](https://github.com/lunatictiol/halo/actions/runs/40516277310) | **failed, stale**: `config/default.toml` changed since results commit `02e4133`; results config differs from HEAD |
  | [#11](https://github.com/lunatictiol/halo/pull/11), push 2 | same, gate re-run (results at `19b74f5`) | [40516650300](https://github.com/lunatictiol/halo/actions/runs/40516650300) | **failed, threshold**: R@5 0.8812 (−0.0561), MRR 0.7307 (−0.0847), max drop 0.005 |

  Lint and tests passed in all three runs; only the gate step failed on #11. #11 was closed unmerged.
- [x] **Thresholds and the baseline file are documented in DECISIONS.md** (D40): R@5 and MRR, `max_drop = 0.005` absolute (one query of 303 = 0.0033). Baseline at commit `02e4133`: hybrid_rerank, `full` index, `dev_sample`, n = 303, R@5 0.9373, MRR 0.8154, equal to the M6 graph's first-attempt retrieval.

Other checks: two consecutive `ci run`s at `02e4133` gave identical top-10 rankings for all 303 queries. `uv run pytest`: 97 passed (9 new for the gate). `uv run ruff check .`: clean.
