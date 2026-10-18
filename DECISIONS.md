# DECISIONS.md — design decision log

Each entry: what was chosen, alternatives, why, and the number that justified it (from `results/`, never from memory).

---

## M0 — Setup and data audit

### D1. Corpus: official Open RAG Bench 1,000 papers, not the local 1,001
- **Chosen:** Vectara's official set from Hugging Face: 396 source + 604 distractors; PDFs downloaded from arXiv.
- **Alternatives:** (a) the local repackaging (396 + 605 third-party distractors); (b) both sets combined (1,605 papers).
- **Why:** results are comparable to published Open RAG Bench numbers and the corpus provenance is known. The local distractors were chosen by an unknown process.
- **Evidence:** `results/m0_audit.txt` — only 19 of the 605 local distractors are in the official 604.

### D2. Relevance labels: HF section-level qrels; ingestion still parses PDFs
- **Chosen:** use `qrels.json` (one `{doc_id, section_id}` per question) as ground truth; parse PDFs with PyMuPDF ourselves; map our chunks to Vectara section IDs in M1.
- **Alternatives:** (a) paper-level labels only (from `Eval_data.csv`); (b) use Vectara's pre-parsed sections as our chunks and skip PDF parsing.
- **Why:** section-level metrics are what make retrieval evaluation meaningful; (b) would remove ingestion as a real component. Cost: the chunk→section mapping risk moves to M1, where it is measured (unmapped qrels are listed).
- **Evidence:** `results/m0_audit.txt` — 3,045/3,045 qrels resolve to an existing section; section_id equals list position for all.
- **Consequence for M2:** with exactly one relevant section per question, recall@k is hit@k and MRR is the most informative ranking metric; nDCG@10 reduces to `1/log2(rank+1)` and is kept only for comparability.

### D3. Environment: uv + Python 3.12
- **Chosen:** uv, `.python-version` = 3.12.
- **Alternatives:** system Python 3.13 with venv/pip; conda.
- **Why:** 3.12 has the most reliable Windows wheels for torch / sentence-transformers; uv gives a lockfile (`uv.lock`) for a reproducible fresh clone (M6 gate).

### D4. Abstention: 20 source papers held out permanently
- **Chosen:** `held_out` = 20 seeded-random source papers that are never indexed, at dev or full scale; their questions form `abstention_set`.
- **Alternatives:** exclude them only from `dev_slice` (the abstention set would become answerable in M6).
- **Why:** keeps the abstention test valid at full scale. Full index is 980 papers.
- **Known caveat:** another paper could genuinely answer a held-out question; the M2 judge spot-checks a sample.
- **Evidence:** `results/m0_splits_report.txt` — 20 papers, 152 abstention questions.

### D5. dev_slice size: ~100 papers instead of 50
- **Chosen:** add seeded-random source papers until ≥300 questions (`dev_sample_min_questions`), plus 60 distractors.
- **Alternatives:** 20 source + 30 distractors (the original spec) with a ~150-question dev_sample; or a dev_sample drawn from the whole corpus (breaks retrieval eval until M6).
- **Why:** papers have ~7.7 questions each, so 20 source papers cannot give ~300 questions. 300 questions gives tighter per-modality estimates; indexing ~100 papers locally is still cheap.
- **Evidence:** `results/m0_audit.txt` (mean 7.69 questions/paper); `results/m0_splits_report.txt` — 43 source papers → 303 questions; dev_slice = 103 papers.

### D6. dev_sample: paper-level sampling, one seed, never re-rolled
- **Chosen:** keep all questions of the selected papers; report metrics by type and by modality separately (never the 8-cell type × modality cross).
- **Alternatives:** balance the 8 cells explicitly.
- **Why:** questions come attached to papers; cell-balancing over-represents rare cells and complicates indexing. Re-rolling the seed for a nicer distribution would be silent cherry-picking. The smallest cells would hold ~4 questions, too few to report.
- **Evidence:** `results/m0_splits_report.txt` — dev_sample vs full: abstractive 59.1% vs 58.6%; text 67.3% vs 62.3%, text-image 23.8% vs 25.4%, text-table 4.3% vs 5.0%, text-table-image 4.6% vs 7.3%. Roughly matches; text is ~5 pp over-represented, which slightly favours a text-only MVP — noted, not corrected.

### D7. Distractors in dev_slice: same primary arXiv category as the dev sources
- **Chosen:** sample 60 distractors whose primary category (`categories[0]`) appears among the dev source papers; random top-up only if too few match.
- **Alternatives:** 60 random distractors.
- **Why:** off-topic distractors are easy to reject, which would inflate dev retrieval metrics and hide the M6 drop.
- **Evidence:** `results/m0_splits_report.txt` — 60/60 category-matched.

### D8. `full` split = answerable questions only
- **Chosen:** `full` = 2,893 questions (3,045 − 152 abstention); abstention questions live only in `abstention_set`.
- **Alternatives:** one 3,045-question list tagged answerable/should-abstain.
- **Why:** one list per role; nothing gets accidentally averaged together.

### D9. Split files: sorted JSON + input hashes, byte-reproducible
- **Chosen:** `splits/<name>.json`, `sort_keys=True`, sorted ID lists, header with seed and SHA-256 of the input files; `.gitattributes` disables line-ending conversion for them.
- **Why:** the M0 gate needs "regenerate → identical"; byte comparison is the strictest check, and input hashes detect an upstream dataset change.
- **Evidence:** `make_splits.py --check` → all 5 files byte-identical (`results/m0_splits_report.txt`).

### D10. Generation LLM: qwen3:8b (local)
- **Chosen:** `qwen3:8b` via Ollama, Q4 (5.2 GB), name in `config/default.toml`.
- **Alternatives:** `qwen3:4b` (faster, weaker); 12–14B local models (heavier CPU offload); a hosted model (Gemini/Claude).
- **Why:** the strongest model that runs at a usable speed on the 6 GB RTX 4050, and it keeps the system fully local. A hosted model is a one-line config swap, to be justified by an M2 measurement if the LLM turns out to be the bottleneck.
- **Evidence:** `results/m0_llm_bench.json` — median 17.7 generated tokens/s; Ollama runs it 30% CPU / 70% GPU (does not fully fit in VRAM).

### D11. Download politeness
- **Chosen:** arXiv PDFs fetched sequentially, 3 s between requests, 5 retries with exponential backoff; HF files in parallel (8 workers). Atomic writes, PDF magic-byte validation, skips existing files.
- **Why:** arXiv's automated-access guidance is ≤1 request / 3 s. The first run hit transient throttling (25 × HTTP 406, 46 × dropped connections out of ~585); manual retries of those URLs returned 200. A re-run against `arxiv.org` kept failing, so PDFs are now fetched from `export.arxiv.org` (arXiv's designated host for automated clients, `data.arxiv_pdf_host`); that run completed all remaining PDFs.
- **Evidence:** `results/m0_audit.txt` — 1,000/1,000 valid PDFs present.

---

## M1 — Ingestion and dense index

### D12. Chunk → section mapping by word 5-gram overlap, not PDF heading detection
- **Chosen:** each PyMuPDF text block is assigned the Vectara section (`corpus/<doc_id>.json`) that contains the largest share of its lowercase word 5-grams. Blocks below `min_match` (page numbers, running headers, references, math-only lines) inherit the previous block's section. Chunks are then built inside each mapped section, so `section_id` comes from the mapping, not from a separate heading parser.
- **Alternatives:** (a) detect headings in the PDF (font size / numbering) and match them to Vectara headings; (b) chunk Vectara's markdown directly.
- **Why:** Vectara's sections don't follow the paper's own headings (e.g. `2401.01872v2`: 9 sections of 123–38,857 chars; its "Abstract" section also contains the introduction), so (a) would have to reproduce Vectara's segmentation from fonts — fragile. (b) has no page numbers, which M5 citations need, and removes PDF parsing as a real component (D2). Overlap mapping is exact wherever the PDF text and Vectara's markdown agree.
- **Evidence:** `results/m1_mapping.txt` — 228/228 dev_sample gold sections have a chunk; over the 5-grams visible in the PDF text, gold-section recall is median 1.00 / mean 0.98, 4/228 below 0.5. Recall excludes 5-grams that never appear in the PDF text (LaTeX, table markdown), which no PDF parser could recover. Worst case `2411.15293v2` s1: 78% of its 5-grams also occur in s0 (Vectara duplicated the "Highlights" text), and ties go to the earlier section — an ambiguity in the labels, not a mapping error.

### D13. `min_match` = 0.3, `shingle_n` = 5
- **Chosen:** 5-word shingles; a block needs ≥30% of its 5-grams in one section to set the section.
- **Alternatives:** swept `min_match` ∈ {0.1, 0.2, 0.3, 0.5, 0.7}.
- **Why:** coverage (228/228) and recall (median 1.00, mean 0.98) are identical across the whole sweep; only the share of inherited words changes (21.6% → 39.8%). 0.3 sits well above the noise floor of chance 5-gram matches while inheriting only a quarter of the words. 5-grams are long enough that common phrases ("in this paper we") rarely tip a block toward the wrong section.
- **Evidence:** `results/m1_mapping.txt` (sweep table, 24.9% inherited words at 0.3). By block count 68.8% of blocks are inherited (`results/m1_gate.txt`) — most blocks are one-line fragments (page numbers, equation lines) with too few words to match.

### D14. Chunk size 300 words, 50-word overlap, chunks never cross a section
- **Chosen:** consecutive blocks of one section are split into 300-word windows with a 50-word overlap; each chunk records the page of its first word (`page`) and last word (`page_end`).
- **Alternatives:** token-based windows; 150 / 500 words; one chunk per section.
- **Why:** ~300 words ≈ 400–450 tokens is well inside nomic-embed-text's context and keeps a chunk about one idea; overlap stops a sentence cut at a boundary from being lost. Never crossing sections keeps `section_id` exact and gives even tiny sections (123 chars) their own chunk — which is what makes every gold section coverable. One chunk per section was rejected because Vectara sections reach ~39k chars. **Not tuned yet:** this is a starting value, to be measured once the M2 harness exists.
- **Evidence:** `results/m1_gate.txt` — 6,740 chunks for 103 papers (median 59 per paper).

### D15. Embedding and index details
- **Chosen:** nomic-embed-text through Ollama `/api/embed` with the `search_document: ` / `search_query: ` prefixes; Qdrant embedded mode at `data/index/qdrant`, one collection per split, cosine distance; point ID = `uuid5(paper_id, chunk_idx)`; re-ingesting a paper deletes its points and upserts new ones.
- **Why:** nomic-embed-text was trained with those task prefixes. Deterministic IDs plus delete-then-upsert make ingestion idempotent and leave no stale chunks if a paper's chunk count changes. Plain `urllib` avoids an SDK dependency for one endpoint.
- **Evidence:** `results/m1_gate.txt` — two consecutive runs give 6,740 → 6,740 chunks, no duplicate `(paper_id, chunk_idx)`, byte-identical ids and texts.
- **Known limitation:** `section_title` is the first markdown heading of the Vectara section, which is sometimes a fragment (e.g. `strap repetitions.`) or misleading (`REFERENCES` on a body chunk of `2408.07379v2` s0). It is display metadata only and not used for retrieval or metrics.
