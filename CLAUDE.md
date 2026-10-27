# CLAUDE.md — HALO (Grounded Knowledge Engine), MVP build

## What this project is

HALO is a question-answering engine over a hard research-paper corpus. It retrieves with hybrid search, reranks, checks whether the evidence actually answers the question, retries with a rewritten query when it doesn't, answers with citations, and **abstains** when the corpus can't support an answer.

Its purpose is a portfolio project for AI engineering roles. Every claim in the README must be backed by a number produced by the eval harness in this repo. A feature without a measured before/after is not done.

**Core rule: build the eval harness before optimizing anything.** No retrieval or generation improvement starts until Milestone 2 passes its gate.

---

## How to work with me (rules for Claude Code)

1. **One milestone at a time.** Finish the current milestone, run its gate checks, report the results, then **stop and wait for my go-ahead**. Do not start the next milestone on your own.
2. **Design before code.** At the start of each milestone, give a short plan: components, data flow, files touched, and trade-offs. Wait for my approval before writing code.
3. **I must be able to defend every line in an interview.** For each non-obvious choice (chunk size, k values, fusion constant, prompt design, thresholds), add an entry to `DECISIONS.md` covering what was chosen, the alternatives, why, and the metric that justified it.
4. **Never invent data formats.** If you're unsure about a dataset field, a qrels format, or a library API, inspect the actual data or docs first. Document findings in `DATA.md`.
5. **No fabricated numbers.** Metrics in README, DECISIONS.md or commit messages must come from a saved results file in `results/`.
6. **Keep changes small and reviewable.** Prefer small, focused commits, one per logical change.
7. **Ask when blocked.** If a gate fails and the fix needs a design change, explain the failure and propose options rather than silently changing scope.
8. **Write milestone notes.** After each milestone's gate passes, append a section to `MILESTONE_NOTES.md` explaining what was done, how it was done, and why (key choices, problems hit, gate results with links to `results/` files). Written for me to study for interviews. This file is gitignored — never commit it.

---

## Scope

### In scope (MVP)
- Text-only parsing of PDFs (no image/table understanding).
- Dense + BM25 hybrid retrieval with Reciprocal Rank Fusion (RRF).
- Cross-encoder reranking.
- LangGraph corrective loop: grade evidence → rewrite query → retry (bounded) → answer or abstain.
- Answers with citations (paper, section, page), plus a check that citations support the answer.
- Evaluation harness: retrieval metrics, answer metrics, abstention metrics, all broken down by question type and modality.
- Scale from a ~100-paper dev slice to the full 1,000-paper corpus.

### Out of scope (backlog, do NOT build unless I ask)
- Vision-language parsing of figures/tables.
- Graph index, summary index, multi-index routing.
- Bounding-box citations.
- Cloud deployment.

(CI regression gate, the web frontend and Docker moved into scope as M8, M10 and M11.)

---

## Dataset

**Primary corpus: Vectara Open RAG Bench, official release** (`huggingface.co/datasets/vectara/open_ragbench`, `pdf/arxiv/`).
- 1,000 arXiv papers: 396 source papers + 604 official Vectara distractors. PDFs are downloaded from arXiv by ID.
- The local `All_PDFs.csv` / `data/pdfs/` set (605 third-party distractors, only 19 overlapping the official ones) is **not** used as the corpus — unknown provenance and not comparable to published results. The 396 source PDFs on disk are reused.
- 3,045 Q&A pairs, labeled `type` (abstractive/extractive) and `source` modality (`text`, `text-image`, `text-table`, `text-table-image`). Query IDs match between `Eval_data.csv` and HF `queries.json`.
- qrels (`qrels.json`, inspected in M0): `{query_id: {"doc_id": "<arxiv id>", "section_id": <int>}}` — **exactly one relevant section per question**. Section IDs index into the `sections` list of the HF corpus JSON (`corpus/<doc_id>.json`, Vectara's own markdown parse). Our PyMuPDF chunks must be mapped to these section IDs in M1.
- Implication for metrics: with one relevant section, recall@k is hit@k and MRR is the most informative retrieval metric.

**Evaluation splits (created in M0, one fixed seed — never re-rolled to get a nicer distribution — committed to the repo):**
- `held_out`: 20 source papers that are **never indexed**, at dev or full scale.
- `abstention_set`: all questions of the `held_out` papers. The correct behavior is to abstain. Caveat: another paper could genuinely answer one; the M2 judge spot-checks a sample.
- `dev_slice`: ~100 papers = 40 source papers (disjoint from `held_out`) + 60 official distractors drawn from the same arXiv categories as those 40. Used for all iteration.
- `dev_sample`: all questions of the 40 dev source papers (≥300). Selected at paper level (seeded random papers until ≥300 questions), not cell-balanced. Its type × modality distribution is printed next to the full set's. Metrics are reported by type and by modality separately, never by the 8-cell cross (cells too small).
- `full`: all answerable questions (~2,895 = 3,045 minus `abstention_set`), run only at milestone completion. Abstention questions stay in their own split.
- Format: one `splits/<name>.json` per split with sorted IDs (`paper_ids`, `query_ids`), a header with the seed and SHA-256 of the source files. Regenerating with the same seed must produce byte-identical files.

Because the MVP is text-only, **text-modality questions are the primary metric.** Image/table questions are still evaluated and reported separately so the gap is visible.

---

## Architecture

**Ingestion:** PDF → text extraction per page → section-aware chunking (keep section title, section id, page number, paper id on every chunk) → embeddings → vector store. The same chunks also go into a BM25 index.

**Query pipeline (LangGraph):**
1. **Retrieve.** Dense top-k and BM25 top-k run in parallel and are fused with RRF.
2. **Rerank.** A cross-encoder reranks the fused candidates and keeps the top-n.
3. **Grade.** An LLM judges whether the evidence is sufficient to answer.
4. **Branch on the grade:**
   - Sufficient → generate the answer with citations.
   - Insufficient and retries remain → rewrite the query, go back to Retrieve (max 2 retries).
   - Insufficient and no retries left → abstain with a reason.
5. **Verify.** A citation check confirms each cited chunk supports its claim. Unsupported claims are flagged or removed.

**Evaluation harness:** It runs any pipeline configuration against a split and writes a results JSON containing the config, git commit, timestamp, and all metrics, overall and per question type and modality.

---

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12, managed with uv | Pinned for torch / sentence-transformers wheel safety on Windows |
| Orchestration | LangGraph | Corrective loop as an explicit state graph |
| LLM (generation, grading) | Ollama, qwen3:8b | Local. Best model that fits the 6 GB RTX 4050 at Q4. Keep the model name in config, not code; a hosted model (Gemini/Claude) is a measured config swap if M2 shows the LLM is the bottleneck |
| LLM judge (eval only) | Configurable: local model or Gemini | Record which judge produced each result |
| Embeddings | nomic-embed-text via Ollama | |
| Vector store | Qdrant in local/embedded mode | No server needed for MVP |
| Sparse retrieval | BM25 library (decide in M3, record in DECISIONS.md) | |
| Reranker | Cross-encoder (e.g. a bge reranker) via sentence-transformers | |
| PDF parsing | PyMuPDF | Text only |
| API | FastAPI | Minimal: one query endpoint + health |
| Tests | pytest | Metric functions must have unit tests |

All tunable values (k, n, RRF constant, retry limit, model names, thresholds) live in a config file. No magic numbers in code.

---

## Repository layout

    halo/
    ├── CLAUDE.md
    ├── README.md            # results table generated from results/
    ├── DATA.md              # dataset formats, as actually inspected
    ├── DECISIONS.md         # design decision log
    ├── MILESTONE_NOTES.md   # what/how/why per milestone (gitignored, personal study notes)
    ├── config/              # pipeline configs (baseline, hybrid, full, ...)
    ├── data/                # raw + processed data (entirely gitignored; rebuilt by scripts/download_data.py)
    ├── scripts/             # download_data.py, audit_data.py, make_splits.py
    ├── splits/              # held_out, abstention_set, dev_slice, dev_sample, full (committed)
    ├── halo/
    │   ├── ingest/          # parsing, chunking, indexing
    │   ├── retrieve/        # dense, bm25, fusion, rerank
    │   ├── graph/           # LangGraph nodes + graph definition
    │   ├── generate/        # answer generation + citation check
    │   └── api/             # FastAPI app
    ├── eval/
    │   ├── metrics/         # retrieval, answer, abstention, citation metrics
    │   ├── runners/         # run a config against a split
    │   └── report/          # build README tables from results
    ├── results/             # one JSON per eval run (committed)
    └── tests/

---

## Milestones

Rough hour estimates assume 1–2 hours/day. Each gate must pass before moving on.

### M0 — Setup and data audit (≈3–4 h)
**Build:**
- Repo scaffold: git repo, `.gitignore`, uv environment on Python 3.12.
- Ollama models pulled (`qwen3:8b`, `nomic-embed-text`); measure and log `qwen3:8b` tokens/sec on the RTX 4050 (6 GB).
- `scripts/download_data.py`: fetch HF `queries.json`, `answers.json`, `qrels.json`, `pdf_urls.json`, `corpus/*.json`, and the PDFs of all 1,000 official papers from arXiv (reusing the 396 source PDFs already on disk). Idempotent, skips existing files.
- Inspect every file and document the real schemas in `DATA.md`: fields, ID formats, how qrels map questions to sections, and why the local 605-distractor set was replaced.
- `scripts/make_splits.py`: create and commit `held_out`, `abstention_set`, `dev_slice`, `dev_sample`, `full` with one fixed seed (see Dataset).
- DECISIONS.md entries for: official corpus over local distractors, dev_slice size change (50 → ~100), paper-level held-out set, category-matched distractors, uv + Python 3.12.

**Gate:**
- [ ] A data-audit script prints counts that match the published numbers (1,000 papers = 396 source + 604 distractors, 3,045 questions, 3,045 qrels), or explains any discrepancy.
- [ ] `DATA.md` describes the qrels format with a real example.
- [ ] Split files are committed; regenerating them with the same seed produces byte-identical files (hash compare).
- [ ] `dev_sample` distribution by question type and by modality is printed next to the full set's and roughly matches.
- [ ] `held_out` papers are disjoint from `dev_slice`; no `abstention_set` question appears in `dev_sample` or `full`.
- [ ] `MILESTONE_NOTES.md` has an M0 section.

### M1 — Ingestion and dense index (≈5–6 h)
**Build:**
- Page-level text extraction.
- Section-aware chunking with metadata (paper id, section id, section title, page).
- Embedding and a Qdrant local index for `dev_slice`.
- A way to map each chunk to the qrels section IDs.

**Gate:**
- [ ] 100% of chunks carry paper id, section id and page.
- [ ] Every qrels section for `dev_slice` questions maps to at least one chunk; unmapped ones are listed and explained.
- [ ] Re-running ingestion is idempotent (same chunk count, no duplicates).
- [ ] Five manual spot-check queries return plausibly relevant chunks (show them).

### M2 — Eval harness and naive baseline (≈8–10 h)
**Build:**
- Retrieval metrics: recall@5, recall@10, MRR, nDCG@10, computed against qrels.
- Answer metrics: faithfulness (LLM judge: is the answer supported by retrieved context?) and correctness vs reference answer (LLM judge).
- Abstention metrics: abstention rate on `abstention_set`, false-abstention rate on answerable questions.
- Results JSON writer (config, commit, judge model, per-slice breakdowns).
- Naive baseline: dense top-k → LLM answer, no reranking, no loop.

**Gate:**
- [ ] Unit tests for every metric function pass on hand-made toy cases with known answers.
- [ ] Two consecutive retrieval-metric runs on `dev_sample` give identical numbers.
- [ ] Baseline results file exists and a summary table prints (overall + per modality + per question type).
- [ ] 10 judge verdicts are shown for me to manually check judge sanity. Record the agreement rate in DECISIONS.md.

### M3 — Hybrid retrieval and reranking (≈6–8 h)
**Build:**
- BM25 index over the same chunks.
- RRF fusion of dense and BM25.
- Cross-encoder reranking of fused candidates.

**Gate:**
- [ ] Ablation table on `dev_sample`: dense only / BM25 only / hybrid (RRF) / hybrid + rerank, with retrieval metrics and latency per query.
- [ ] The chosen configuration and the reason for it are recorded in DECISIONS.md with the numbers.
- [ ] If hybrid or rerank does NOT improve metrics, report that honestly and investigate before proceeding.

### M4 — Corrective loop and abstention (≈8–10 h)
**Build:**
- LangGraph state graph: retrieve → rerank → grade → (rewrite → retrieve, max 2 retries) → generate or abstain.
- Grader prompt and query-rewrite prompt, both versioned in config.
- The abstention response includes a short reason.

**Gate:**
- [ ] A graph diagram (generated from the graph definition) is saved to the repo.
- [ ] Across the full `dev_sample` run, no query exceeds the retry limit (logged).
- [ ] Comparison vs M3 on answer metrics, abstention rate on `abstention_set`, false-abstention rate, and average retries per query.
- [ ] 5 examples where the rewrite loop rescued a failed first retrieval, and 5 correct abstentions, are saved for the README.

### M5 — Citations and grounding check (≈4–5 h)
**Build:**
- Answers cite (paper, section, page) inline.
- A post-generation check verifies each cited chunk supports its sentence; unsupported claims are flagged.
- Citation metrics: citation validity (cited chunk supports claim) and citation coverage (share of answer sentences with a citation).

**Gate:**
- [ ] Citation validity and coverage are measured on `dev_sample` and saved.
- [ ] Faithfulness after the grounding check is compared with M4.
- [ ] 10 answers with citations are shown for my manual review.

### M6 — Scale, API and ship (≈5–6 h)
**Build:**
- Ingest all 980 indexable papers (1,000 minus the 20 `held_out` papers).
- Run the final configuration on the `full` split.
- Minimal FastAPI query endpoint and CLI.
- README generated from results files: what HALO does, architecture diagram, results table showing the progression (baseline → hybrid → rerank → corrective loop → grounded), rescued-query and abstention examples, known limitations (image/table questions), backlog.

**Gate:**
- [ ] A fresh clone plus the README quickstart runs a query end-to-end.
- [ ] Every number in the README traces to a file in `results/`.
- [ ] Full-corpus metrics are reported next to the dev-slice metrics, with an explanation of any drop (distractors now included).
- [ ] Known limitations are written honestly.

---

## Post-MVP milestones (M7–M11)

Same rules as M0–M6: plan first, one milestone at a time, gate before moving on, every number from `results/`. Order matters: M7 makes the judge trustworthy before M9 produces new judged numbers.

### M7 — Judge calibration (≈3–4 h)
**Build:**
- Finish the pending M2 manual review (D18 status), then extend it to a hand-labeled calibration set of ~50 verdicts (correctness + faithfulness, seeded sample from `dev_sample` runs, negatives oversampled). Labels saved in `eval/calibration/`.
- A second judge from a different model family (Gemini or Claude, configured in `[judge]`), so the generator no longer grades itself.
- Agreement script: raw agreement and Cohen's κ of each judge vs my labels, per verdict kind.
- Re-score the M6 headline runs (`m6_graph_dev_sample`, `m6_graph_full`, `m6_graph_abstention_set`) with the chosen judge from saved answers. No re-generation.

**Gate:**
- [ ] κ for both judges against my labels is saved to `results/m7_judge_calibration.md`.
- [ ] The chosen judge and the reason (with κ) are recorded in DECISIONS.md, and D18's "not done yet" status is closed.
- [ ] README results are regenerated with the chosen judge, and any number that moved is called out.
- [ ] The citation-validity gap (self-check 0.971 vs manual 7/10) is stated in README limitations.

### M8 — CI regression gate (≈3–4 h)
**Build:**
- GitHub Actions workflow: lint, then `pytest`, then the regression gate.
- Regression gate on deterministic retrieval metrics (R@5, MRR) on `dev_sample`, with thresholds in config compared against a committed baseline file. LLM metrics stay out of CI (non-deterministic, slow).
- Open design question for the M8 plan: the index and Ollama aren't available on a hosted runner. Options: (a) a self-hosted runner on this machine, (b) the gate checks a committed results JSON whose `git_commit` must match the PR head, (c) a small cached fixture index. Pick one, record it in DECISIONS.md.

**Gate:**
- [ ] A PR with a deliberately degraded config (e.g. `rerank` off) fails the gate; a clean PR passes. Both runs are linked.
- [ ] Thresholds and the baseline file are documented in DECISIONS.md.

### M9 — Contextual enrichment and chunking benchmark (≈8–10 h)
**Build:**
- Three chunking strategies over the same `dev_slice`: the current section-aware chunker, fixed-size with overlap, and section-aware + contextual enrichment (1–2 LLM-generated lines prepended to each chunk before embedding and BM25, describing paper and section). Each goes in its own Qdrant collection; enrichment is cached by chunk content hash so re-runs are free.
- Optional fourth: parent–child retrieval (retrieve small chunks, generate from the parent section). Only if the first three finish in budget.
- Retrieval ablation on all strategies, then full pipeline on the best one, judged with the M7 judge.

**Gate:**
- [ ] Table and a chart in README: R@5, R@10, MRR, nDCG@10 per strategy on `dev_sample`, plus ingest time and enrichment cost.
- [ ] End-to-end Correct / Faithful / abstention for the chosen strategy vs M6 on `dev_sample` and `abstention_set`. Most M6 failures were generation misses (216 of 427), not retrieval, so a retrieval gain may not move Correct; report it either way.
- [ ] If adopted, the full index is rebuilt and the `full` split re-run; DECISIONS.md has the entry with numbers. If not adopted, say why.

### M10 — Streaming API and web frontend (≈6–8 h)
**Build:**
- `POST /query/stream`: Server-Sent Events from the LangGraph run, one event per node (retrieve, rerank, grade, rewrite, generate, check) with timing, then the final answer and citations. The existing `/query` stays.
- Frontend: htmx + Jinja2 templates served by FastAPI (no npm, no build step), htmx SSE extension. A question box; live step indicators showing the corrective loop (including rewrites and retries); the answer with citation chips (paper, section, page) linking to the arXiv PDF at that page; abstentions shown with their reason; flagged/unsupported sentences visibly marked.
- Still one query at a time (D37): a second request while one runs gets a clear "busy" response.

**Gate:**
- [ ] Endpoint tests: event order, final event matches `/query` output for the same question, busy handling.
- [ ] Manual demo on three saved questions: one direct answer, one rescued by a rewrite, one abstention. Screenshots or a GIF saved for the README.
- [ ] Time-to-first-event and total latency recorded in `results/`.

### M11 — Docker (≈3–4 h)
**Build:**
- `Dockerfile` for the app (uv, Python 3.12, CPU and CUDA variants or a build arg) and `docker-compose.yml` with the app and an Ollama service (GPU via NVIDIA Container Toolkit / WSL2; models pulled on first start).
- Data and the Qdrant index mounted as volumes, not baked into the image. A documented one-command path to build the index inside the container.
- Health/readiness check that waits for Ollama and the index.

**Gate:**
- [ ] On a clean checkout, `docker compose up` plus the documented index step serves the M10 frontend and answers a query end-to-end.
- [ ] README quickstart has a Docker path next to the uv path; image size and cold-start time recorded.

---

## Definition of done (MVP)
- All M0–M6 gates pass.
- README shows a measured improvement at each stage over the naive baseline.
- `DECISIONS.md` has an entry for every tuned value and major design choice.
- I can explain the architecture, every metric, and every decision without reading notes.

## Backlog (post-MVP, in priority order)
1. Expose HALO as an MCP server.
2. Abstention drift at full scale (0.862 → 0.776): scope check or a grader threshold calibrated on the full index.
3. Table/figure understanding for image and table questions.
4. Query routing and additional indexes.
5. Cloud deployment.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
