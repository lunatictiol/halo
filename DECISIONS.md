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

## M2 — Eval harness and naive baseline

### D16. Retrieval metrics: first gold chunk in the chunk ranking, k = 5 / 10
- **Chosen:** the ranking is the list of chunks the retriever returns (what the generator sees). A chunk is relevant iff its `(paper_id, section_id)` equals the single qrels section; only the first such chunk counts. Reported: recall@5, recall@10 (= hit@k), MRR, nDCG@10, and a diagnostic paper-level hit@10.
- **Alternatives:** (a) dedupe chunks to a section ranking first; (b) count every gold-section chunk as relevant (graded nDCG).
- **Why:** with exactly one relevant section per question (DATA.md, qrels format), counting only the first gold chunk gives each query one relevant item, so the metrics have their textbook meaning: recall@k is hit@k, MRR = 1/rank, and nDCG@10 = 1/log2(rank+1) because IDCG = 1 (so nDCG@10 is close to MRR and adds little; it is kept because it is the standard BEIR-style headline). (a) would make "k" mean k sections while the generator actually gets k chunks. (b) would reward retrieving several chunks of the same section, which a long section gets for free. Paper hit@10 separates "wrong paper" from "right paper, wrong section".
- **Evidence:** `results/m2_baseline_dev_sample.json` — recall@5 0.868, recall@10 0.927, MRR 0.707, nDCG@10 0.761; paper hit@10 0.993, so almost all misses are section-level, not paper-level. Determinism: `results/m2_gate.txt`.

### D17. Answer and abstention metric definitions
- **Chosen:** binary per-query scores averaged per slice. *Faithfulness* (judge: every claim supported by the top-5 context) over answered questions only. *Correctness* (judge vs reference answer) over all answerable questions with a refusal counted wrong, plus *correct|answered*. *False-abstention rate* on `dev_sample`; *abstention rate* on `abstention_set`. Missing values (abstained, or judge error) are excluded from means, never scored 0, and `n` is reported next to each mean.
- **Abstention detection:** the generator must output the exact sentinel `INSUFFICIENT_EVIDENCE`; any occurrence counts. A string match, not a judge, so abstention metrics carry no judge noise.
- **Alternatives:** a 1–5 Likert judge; RAGAS-style claim decomposition; a judge deciding whether an answer is a refusal.
- **Why:** binary labels are easy to audit by hand (the M2 sanity check) and to explain; claim decomposition multiplies judge calls on a 17.7 tok/s local model. Splitting correctness into "all" and "answered only" keeps a model from gaming one number by refusing more.
- **Evidence:** `results/m2_baseline_dev_sample.json` — faithfulness 0.975 (n=284), correctness 0.848 (n=303), correct|answered 0.905, false-abstention 0.063. `results/m2_baseline_abstention_set.json` — abstention rate 0.875 (n=152).

### D18. LLM judge: qwen3:8b, schema-constrained JSON, reason before verdict
- **Chosen:** the judge is the same local qwen3:8b as the generator, temperature 0, `think: false`, output constrained by an Ollama JSON schema `{reason, verdict ∈ enum}` with `reason` first. Unparseable output is retried once with a doubled token budget, then recorded as a judge error (verdict None), never guessed. Prompts are versioned in `config/default.toml` (`judge-v1`) and the judge model is written into every results file.
- **Alternatives:** Gemini as judge (no self-preference, needs an API key and dependency); free-text verdicts parsed by regex.
- **Why:** zero cost and no key for the MVP; swapping the judge is a config change. Schema-constrained decoding makes malformed output nearly impossible; putting the reason first makes the model state its evidence before the label. **Known risk — self-preference:** the judge grades its own model's answers. The manual sample (D20) measures this.
- **Measured (M7, D39):** against 50 blind human labels, κ 0.48 on faithfulness and 0.56 on correctness (moderate). The bias runs in opposite directions: lenient on faithfulness (4 of 17 sampled "supported" were unsupported to me), strict on correctness (4 of 10 sampled "incorrect" were correct to me). Kept as the judge: the different-family llama3.1:8b scored lower on both.
- **Evidence:** 0 judge errors in 568 dev_sample calls and 19 abstention_set calls.

### D19. Naive baseline settings: k_context = 5 chunks, num_ctx = 8192, thinking off
- **Chosen:** dense top-10 is retrieved (for metrics); the top 5 chunks (~2k words) go to the generator. `num_ctx` is set explicitly to 8192 and `halo/llm.py` raises if prompt + output reach it. qwen3 thinking mode is off for generation and judging.
- **Alternatives:** 10 chunks of context; Ollama's default context window; thinking on.
- **Why:** 5 chunks already contain the gold section for 86.8% of questions (recall@5) while halving prompt size versus 10 — less noise for an 8B model and faster on 6 GB of VRAM. Ollama's default window is smaller than the prompt and truncates silently, which would corrupt both answers and faithfulness judgements. Thinking multiplies output tokens at 17.7 tok/s (`results/m0_llm_bench.json`).
- **Evidence:** `results/m2_baseline_dev_sample.json` (`generator_tokens`, `latency_ms_median`): max prompt 3,332 tokens of 8,192, max output 130 tokens, median generation 9.2 s/query.
- **Not tuned:** k_context is a starting value; varying it is an M3/M4 ablation.
- **Traceability note:** generation and judging ran at commit `701e3d2`; the results files were re-scored (score stage only, no LLM calls) at the commit that added `generator_tokens`, which is the commit they record.

### D20. Judge sanity check (manual review of 10 verdicts) — SUPERSEDED by D39
- **Superseded:** replaced by the M7 calibration (D39): 50 blind labels on the final M6 pipeline instead of 10 non-blind ones on the M2 baseline. The 10-item review below was never done.
- **Status: closed by D39** (M7, 50 blind labels). Original M2 status, kept for the record: `results/m2_judge_sample.md` holds 10 verdicts (5 faithfulness, 5 correctness; up to 2 negatives per kind oversampled, seed 20261015). The manual agree/disagree review has **not been done yet**, so no agreement rate is recorded. This entry is filled in once it is.
- **Why it matters:** faithfulness is 0.975 overall and 1.000 on abstractive questions with a self-grading judge (D18) — possible leniency. If agreement is low, options are a stricter judge prompt (`judge-v2`) or a Gemini judge before M3 numbers are produced.

---

## M3 — Hybrid retrieval and reranking

All numbers below: `dev_sample` (n=303), from `results/m3_ablation.md` and the `results/m3_retrieval_*_dev_sample.json` files it cites, unless stated otherwise.

### D21. BM25: `bm25s`, k1 = 1.5, b = 0.75, English stemming + stopwords, built from the Qdrant payloads
- **Chosen:** `bm25s` (sparse-matrix BM25) with PyStemmer English stemming and English stopwords, Lucene-default k1/b. The index is rebuilt in memory per process from the Qdrant payloads, so BM25 and dense always rank exactly the same 6,740 chunks.
- **Alternatives:** `rank_bm25` (simpler, but scores every document in Python per query: slow at 100k chunks in M6); Qdrant sparse vectors (one store, but more moving parts); a persisted BM25 index (faster startup, but can go stale after re-ingestion).
- **Why:** `bm25s` is fast at full-corpus scale and has no server. Rebuilding takes seconds, and this way the two indexes can never drift apart. Persisting the index is left until the API (M6) makes startup time matter. k1/b are not tuned: tuning them on the 303 dev questions would be fitting noise.
- **Evidence:** BM25 alone **beats dense**: R@5 0.924 vs 0.868, MRR 0.758 vs 0.707, median latency 0.2 ms vs 53 ms. Likely reason: Open RAG Bench questions are LLM-generated from the gold section, so they reuse its wording (high lexical overlap). Real user questions paraphrase more, so this advantage may not transfer.

### D22. Fusion: RRF with k = 60, 50 candidates per retriever
- **Chosen:** Reciprocal Rank Fusion, score = Σ 1/(60 + rank), over dense top-50 and BM25 top-50; the fused list is cut to 50. Ties are broken on (paper_id, chunk_idx) so the order is deterministic.
- **Alternatives:** score fusion (min-max normalised or weighted sum of cosine and BM25 scores); weighted RRF; a tuned k.
- **Why:** RRF only uses ranks, so cosine and BM25 scores never need calibrating against each other. k = 60 is the constant from Cormack et al. (2009) and the usual default. Not tuned, for the same reason as D21. 50 candidates give the reranker a ceiling of R@50 = 0.990 (dense alone: 0.980).
- **Evidence (honest result):** hybrid beats dense on every metric (R@5 0.908, R@10 0.967, MRR 0.759) but does **not** beat BM25 alone on R@5 (0.908 vs 0.924); MRR is equal (0.759 vs 0.758). Per query: 13 questions are top-5 for BM25 only, and equal-weight fusion with the weaker dense ranking pushes them out. Fusion regains only 8 dense-only hits. Weighting BM25 higher would probably fix this. It was not tried, because the reranker (D23) removes the gap, and a weight tuned on this benchmark's lexical bias would not generalise.

### D23. Reranker: `BAAI/bge-reranker-v2-m3`, fp16, max_length 512, batch 16
- **Chosen:** sentence-transformers `CrossEncoder` running in fp16 on the RTX 4050. It scores all 50 fused candidates; top 10 are kept for metrics, top 5 go to the generator. Its VRAM is released before generation so qwen3:8b keeps the GPU.
- **Alternatives:** `ms-marco-MiniLM-L-6-v2` (22M parameters, much faster, English MS MARCO web data); `bge-reranker-base` (278M). Neither was measured.
- **Why:** v2-m3 is a strong general-purpose reranker that fits in about 1.1 GB at fp16. 300-word chunks are about 400 tokens, so 512 holds query + chunk in nearly all cases.
- **Evidence:** hybrid → hybrid + rerank: MRR 0.759 → **0.830**, R@5 0.908 → 0.944, nDCG@10 0.810 → 0.865. The gain holds on every slice, including text-table-image MRR (0.576 → 0.784, n=14). Cost: median rerank 807 ms per query (p95 826 ms), 95% of retrieval time.

### D24. Chosen configuration: `hybrid_rerank`
- **Ablation (dev_sample):**

  | Method | R@5 | R@10 | MRR | nDCG@10 | median ms |
  |---|---|---|---|---|---|
  | dense | 0.868 | 0.927 | 0.707 | 0.761 | 53 |
  | bm25 | 0.924 | 0.960 | 0.758 | 0.808 | 0.2 |
  | hybrid | 0.908 | 0.967 | 0.759 | 0.810 | 53 |
  | hybrid_rerank | **0.944** | **0.970** | **0.830** | **0.865** | 849 |
  | bm25_rerank | 0.941 | 0.967 | 0.827 | 0.862 | 836 |

- **Why hybrid_rerank over bm25_rerank:** the two are tied (paired gold ranks: 1 query better, 1 worse). Dense adds about 45 ms to an 800 ms query and covers paraphrased questions, where BM25 has no word overlap to match on. This benchmark under-represents those questions (D21), so their value is a stated **hypothesis, not a measured gain**. Dropping dense remains an option if latency ever matters more.
- **Answer metrics, M2 baseline → M3** (`results/m2_baseline_*.json` → `results/m3_hybrid_rerank_*.json`, same generator, prompts and judge): correctness 0.848 → **0.908**, false-abstention 0.063 → **0.020**, faithfulness 0.975 → 0.987, text-modality correctness 0.868 → 0.951.
- **Regression:** abstention rate on `abstention_set` fell from 0.875 to **0.809** (n=152). The number of answered questions the judge rated supported, i.e. spot-check candidates, rose from 14 to 23. Better retrieval surfaces passages from indexed papers that are closer to the held-out question, and the generator answers from them instead of refusing. Retrieval cannot fix this. It is exactly what M4's evidence grader is meant to catch, and M4 is measured against these numbers.
- **Determinism:** the hybrid_rerank gold rank of every one of the 303 queries is identical between the ablation run and the independent retrieve stage of the answer run (two processes, fp16 GPU reranking).
- **Not caused by M3:** median generation time on dev_sample went from 9.2 s to 13.7 s, with prompt and output token counts nearly unchanged (median prompt 2,126 → 2,266, output 51 → 55). On abstention_set it went down instead (5.0 → 3.3 s), so this is machine-level variance, not the retrieval change.

### D25. Ollama URL: `127.0.0.1`, not `localhost`
- **Chosen:** `ollama_url = "http://127.0.0.1:11434"`.
- **Why:** on Windows, `localhost` resolves to IPv6 `::1` first; Ollama listens on IPv4 only, so every request waited about 2 s before falling back. Measured with the same embed call: 2,128–2,162 ms via `localhost`, 57–98 ms via `127.0.0.1`.
- **Evidence:** the M2 baseline's median retrieve latency (2,184 ms, `results/m2_baseline_dev_sample.json`) was almost entirely this delay. Dense retrieval is now 53 ms median. It also added about 2 s to every M2 generation and judge call. Quality metrics are unaffected (the dense ablation row reproduces M2's retrieval metrics exactly).

### D26. Corrective loop: LangGraph state graph, max_retries = 2, rewritten query for retrieval only
- **Chosen:** `retrieve (hybrid RRF) → rerank → grade → generate | rewrite → retrieve | abstain`, compiled as a LangGraph `StateGraph` (`halo/graph/pipeline.py`, diagram `docs/m4_graph.md`). At most 2 retries, so at most 3 retrieval attempts per question. The retry limit lives in one pure routing function (`route_after_grade`), and the runner recounts retrievals from each query's trace as an independent check (`queries_over_retry_limit` in every M4 results file). The grader and generator always see the user's original question; only retrieval and reranking use the rewritten query. After a retry, the generator gets the hits of the attempt the grader approved, not a merge of all attempts.
- **Alternatives:** a plain Python while-loop (same behaviour, but no explicit graph to draw or extend); 1 or 3 retries; reranking rewritten-query candidates against the original question; merging hits across attempts.
- **Why:** the graph makes the control flow a reviewable artifact and puts the stopping rule in one tested function. 2 retries bounds worst-case cost at about 3× a single attempt, which matters at ~15 s per attempt on this GPU. A third rewrite of the same question has little new to try. Reranking against the rewritten query lets a rewrite that names the missing term actually change the ranking; reranking against the original would largely undo it. Merging attempts would show the generator passages the grader never approved.

### D27. Evidence grader: qwen3:8b, schema-constrained `{reason, verdict}`, strict "different paper" rule
- **Chosen:** one LLM call on the top `k_context` (5) reranked passages, using the judge's JSON-schema pattern (reason before verdict, D18) with labels `sufficient | insufficient`. The prompt (`grade-v1`, versioned in config) says passages that are only on a related topic, or that describe a different method, model, dataset or paper, are insufficient, and that the reason must name what is missing, because that reason is the rewriter's input. A grader parse failure counts as insufficient. The schema/parse/retry code is shared with the judge (`halo.llm.classify`).
- **Alternatives:** a reranker-score threshold (no LLM call, but cross-encoder scores are not calibrated across questions and need a tuned cut-off); letting the generator's sentinel be the only abstention signal (the M3 behaviour); a graded score instead of a binary label.
- **Why:** M3's abstention regression (0.875 → 0.809, D24) comes from the generator answering from close-but-wrong passages of another indexed paper. That is precisely "related topic, different paper", so the grader is told to look for it explicitly. A binary label keeps routing deterministic and matches the judge design. The generator keeps its sentinel as a second line of defence.

### D28. Query rewriter: one line, informed by the grader's reason and all previous queries
- **Chosen:** prompt `rewrite-v1`: original question, every query already tried, and the grader's reason. It asks for one new query that uses the technical terms and quantities the answer would contain, and does not repeat a tried query. The first non-empty line is used; an empty rewrite falls back to the question.
- **Alternatives:** HyDE (generate a hypothetical answer passage and retrieve with it); multi-query expansion fused with RRF; rewriting without the grader's reason.
- **Why:** passing the grader's reason makes the rewrite targeted ("the passages do not give the learning rate" becomes a query about the learning rate) rather than a paraphrase. One query per attempt keeps the cost at one extra short LLM call. HyDE and multi-query are stronger but cost more LLM time per attempt on a 6 GB GPU; they are the next thing to try if rescues are rare.

### D29. GPU sharing: reranker on CUDA, qwen3:8b capped at 22 of 36 layers on the GPU (`num_gpu = 22`)
- **Problem:** M3 released the reranker before a separate generation stage. In the loop, embedding, reranking and LLM calls alternate for every query on one 6 GB RTX 4050. Ollama picks its GPU layer count (~23 for qwen3:8b) without knowing about the reranker's ~1.1 GB, so the two overcommit VRAM and Windows pages both into shared system memory.
- **Measured** (`scripts/bench_rerank_device.py` → `results/m4_rerank_device_bench.json`; 10 dev_sample queries after 2 warm-ups, each scenario in a fresh process with Ollama unloaded first; per attempt = retrieve + rerank + 2 LLM calls):

  | Scenario | Ollama CPU/GPU | rerank ms | LLM call ms | per attempt ms |
  |---|---|---|---|---|
  | (a) reranker on GPU, loaded first, Ollama auto | 36%/64% | 1,598 | 9,980 | 21,779 |
  | (a) reranker on GPU, LLM loaded first, Ollama auto | 36%/64% | 1,543 | 10,148 | 22,037 |
  | (b) reranker on CPU (fp32), Ollama auto | 36%/64% | 39,700 | 5,586 | 50,919 |
  | **(a) + LLM capped at 22 GPU layers** | 41%/59% | 1,427 | **6,370** | **14,376** |
  | (a) + 18 layers | 50%/50% | 1,311 | 17,445 | 36,348 |
  | (a) + 14 layers | 60%/40% | 1,075 | 18,661 | 38,445 |

- **Chosen:** (a) with `[llm] num_gpu = 22`, 34% faster per attempt than Ollama's automatic choice. The LLM call (6.4 s) gets close to its uncontended speed (5.6 s, scenario b, where the reranker is off the GPU), and reranking stays on GPU. Moving the reranker to CPU frees the GPU for the LLM but makes reranking 25× slower. Fewer than 22 layers falls off a cliff (LLM 17–19 s).
- **Quality:** the CPU fp32 and GPU fp16 rerankers gave identical top-5 lists on all 12 queries, so the device choice is purely about speed.
- **Limits:** 20 and 24 layers were not measured (that re-run was killed by host memory pressure). 22 is the best measured point, not a proven optimum, and it is machine-specific: the value lives in config.

### D30. Grader prompt grade-v2: inference from on-topic passages counts as sufficient
- **Problem:** with `grade-v1` (D27) the loop raised abstention on `abstention_set` from 0.809 to 0.934 but cut `dev_sample` correctness from 0.908 to 0.858 (false abstention 0.020 → 0.086; 23 questions correct in M3 became wrong or refused, 8 the other way). In 24 of the 26 grader refusals the gold section was already in the first-attempt top-5. The reasons nearly all read "the passages mention X but do not *explicitly* state …", so v1 demanded verbatim answers, which abstractive questions rarely have (their false abstention went 0.011 → 0.106).
- **Chosen:** `grade-v2`: sufficient when the passages cover the subject the question names and an answer can be stated, summarised or reasonably inferred from them; insufficient only when they are about a different method, model, dataset or paper, or the key entity or quantity does not appear at all. Rewriter, retry limit and generator are unchanged.
- **Alternatives:** keep v1 and accept the drop; on the last attempt let the generator decide instead of the grader (keeps rescues, but the generator alone abstained only 0.809 in M3).
- **Measured** (`results/m4_graph_*.json` = v1, `results/m4_graph_v2_*.json` = v2, M3 = `results/m3_hybrid_rerank_*.json`):

  | | M3 | M4 v1 | **M4 v2** |
  |---|---|---|---|
  | Correct (`dev_sample`) | 0.908 | 0.858 | **0.908** |
  | False abstention | 0.020 | 0.086 | 0.033 |
  | Abstention on `abstention_set` | 0.809 | 0.934 | **0.882** |
  | Avg retries (dev / abstention) | 0 | 0.234 / 1.862 | 0.086 / 1.737 |
  | Paired flips vs M3 (gained / lost) | | 8 / 23 | 8 / 8 |

- **Why v2:** it keeps M3's answer quality (correct 0.908 = 0.908, correct-when-answered 0.926 → 0.939) and still raises abstention by 7.3 points. v1 bought 5 more abstention points with 5 points of correctness on answerable questions, the wrong trade for a QA engine whose questions are mostly answerable. The prompt was changed once, after reading the v1 failures on `dev_sample`. It was not tuned further, and the same split is still the only one it has been measured on, so `full` (M6) is the honest test.

### D31. Citation format: the model cites passage labels, code maps them to (paper, section, page)
- **Chosen:** the generator sees passages labelled `[P1]..[Pn]` and ends each sentence with labels (`[P2]`, `[P1][P3]`). After generation, code replaces each label with `[paper §section p.page]` from that chunk's metadata.
- **Alternatives:** ask the model to write the paper ID, section and page itself; cite at answer level (one source list at the end).
- **Why:** a label can only point at a passage that was actually retrieved, so the model cannot invent a paper ID or page number. A label outside 1..n is recorded as `out_of_range` (invalid, no LLM call). Sentence-level labels are what make a per-sentence support check possible; an answer-level list cannot say which claim came from where.

### D32. Grounding check policy: one LLM check per (sentence, cited passage); remove unsupported, keep uncited but flag
- **Chosen** (`check-v1`, `halo/generate/cite.py`): for each sentence and each passage it cites, qwen3:8b answers `{reason, verdict: supported | unsupported}` (schema-constrained, same `classify` as the grader). A sentence with at least one supported citation is kept, with its unsupported citations stripped. A cited sentence with no supported citation is removed (after re-attribution, D34). An uncited sentence is kept but lowers coverage. If no grounded sentence remains, the answer becomes an abstention ("grounding check: no claim is supported by a cited passage"). A checker parse failure does not keep a sentence (same rule as the grader) and is excluded from validity.
- **Alternatives:** one whole-answer check (cheaper, but cannot say which claim is unsupported); flag-only (keep everything, mark it); also remove uncited sentences (would delete connective or summary sentences the model legitimately leaves uncited).
- **Why:** CLAUDE.md asks for unsupported claims to be flagged *or removed*. Removal is the stricter, user-visible behaviour, and its measured cost is small: 0.5% of sentences removed on `dev_sample` with cite-v2 (`results/m5_cite_v2_dev_sample.json`). Latency cost: median end-to-end 16,214 ms (M4) → 24,922 ms (stitched, D33); the per-pair checks are most of it.

### D33. Citation validity is self-checked; M5 is evaluated by replaying M4's graph checkpoints
- **Validity:** the share of the pre-check answer's citations that the pipeline checker labels supported. It is the checker grading its own pipeline, and it is labelled "self-checked" everywhere. Independent signals: the whole-answer faithfulness judge (pre- and post-check) and the 10-answer manual review in `results/m5_cite_v2_report.md`.
- **Alternatives:** a separate judge model for validity (no second local model fits the 6 GB GPU next to qwen3:8b; Gemini adds a dependency and cost); hand-labelling all ~500 citations (too slow).
- **Replay:** M5 reuses `m4_graph_v2`'s hits, grader verdicts and retries from its `graph.jsonl` and reruns only generate + verify (`--replay-from`). Every difference vs M4 is due to the citation prompt or the check, not to retrieval or grader nondeterminism. Latency is stitched: M4 graph time − M4 generate time + new generate time + verify time.
- **Limit found:** the faithfulness judge rated all 16 check-changed cite-v1 answers faithful *before* the check (`results/m5_cite_dev_sample.json`: `faithful_raw` 0.983 = `faithful` 0.983), so the whole-answer judge is too lenient to see what the per-sentence checker catches. Faithfulness is not the metric that shows the check's value; the removed-sentence examples are.
- **Manual review (cite-v2, 10 seeded answers in `results/m5_cite_v2_report.md`):** the checker kept every sentence of all 10 as grounded; I judged the citations valid in 7/10 (agreement 0.70, vs self-checked validity 0.971). The 3 disagreements: Review 2, a two-part sentence kept because one citation supports one part, while the unsupported part's citation was stripped and the claim stayed; Review 7, an overreaching inference the checker passed; Review 10, an uncited opening "Yes" that contradicts the cited passage (uncited sentences are never checked, D32), plus a table-asterisk inference the checker passed. So self-checked validity overstates real citation quality.

### D34. cite-v2: P-prefixed labels and re-attribution of failed citations
- **Problem (cite-v1, plain `[1]..[n]` labels, `results/m5_cite_dev_sample.json`):** 533 citations: 508 supported, 12 unsupported, 13 out of range. The out-of-range "citations" were the papers' own bibliography markers (`[21][31]`, `[11]`, `[12]`) copied from passage text, and 4 sentences were removed only because of them. Of the 6 correctness losses caused by the check, 3 were correct catches (answers from outside knowledge: QuickSort, inheritance) and 3 were checker misses, 2 of them where the supporting text was in a different retrieved passage than the one cited.
- **Chosen:** (1) passages are labelled `[Pn]` and the parser reads only `[Pn]`; bracketed numbers are stripped as bibliography markers. (2) A cited sentence with no supported citation is checked against the other retrieved passages and re-attributed to the first one that supports it. Validity is still computed on the generator's original citations, so re-attribution does not inflate it; re-attributions are counted separately. `check-v1` is unchanged.
- **Alternatives:** keep v1 and accept the removals; switch to flag-only.
- **Measured** (`results/m5_cite_*.json` = v1, `results/m5_cite_v2_*.json` = v2, M4 = `results/m4_graph_v2_*.json`):

  | | M4 v2 | M5 v1 | **M5 v2** |
  |---|---|---|---|
  | Correct (`dev_sample`) | 0.908 | 0.884 | **0.894** |
  | Correct when answered | 0.939 | 0.927 | 0.928 |
  | Faithful, final answer | 0.986 | 0.983 | 0.980 |
  | False abstention | 0.033 | 0.046 | 0.036 |
  | Citation validity (self-checked) | – | 0.964 | 0.971 |
  | Citation coverage (pre-check / final) | – | 0.941 / 0.940 | 0.927 / 0.929 |
  | Sentences removed | – | 0.027 | 0.005 |
  | Out-of-range citations | – | 13 | 0 |
  | Abstention on `abstention_set` | 0.882 | 0.888 | 0.868 |

- **Why v2:** out-of-range citations go 13 → 0, removed sentences 2.7% → 0.5%, 6 sentences are re-attributed instead of removed, and correctness recovers 0.884 → 0.894. Of the 12 `dev_sample` questions correct in M4 and wrong in v2, 11 had no sentence removed and no grounding abstention, so they come from the reworded generation prompt (8 questions flip the other way); 1 is the check correctly refusing an answer from outside knowledge (inheritance). Abstention on `abstention_set` drops 0.882 → 0.868 for the same reason: the grader's 124 refusals are unchanged (replayed), but under cite-v2 the generator answered 5 questions it refused in M4, against 3 new refusals (2 from the grounding check, 1 from the generator).
- **Caveat:** cite-v2 was designed after reading v1's failures on `dev_sample`, so its dev numbers are optimistic; `full` (M6) is the clean test.

### D35. check-v2: one joint check per sentence, and uncited sentences are checked too
- **Problem:** the 10-answer review of cite-v2 + check-v1 found 3 invalid answers (D33). Two were structural holes in the check: a two-claim sentence kept because one of its passages supported one claim (per-pair checks, "any supported" keeps the sentence), and an uncited sentence contradicting the evidence (uncited sentences were never checked). The third was a loose inference the checker passed.
- **Chosen** (`check-v2`): (B) one check per sentence: "do the cited passages, taken together, support every part of the claim?"; supported → kept with all its citations. (A) A failed *or uncited* sentence is tried against each other passage alone and attributed to the first that supports it, otherwise removed. The prompt wording changed only as far as B needs ("passages taken together", "every part"); it was deliberately not made stricter about inference, to avoid tuning to the 3 examples. Ceiling: a sentence that needs two passages and cited the wrong ones is removed, because attribution tries single passages.
- **Alternatives:** C, a stricter checker prompt (targets loose inference, risks check-v1-era "not explicitly stated" over-refusal and overfitting to the review sample); a stronger checker model (no second model fits the GPU; a hosted one is a config swap to measure).
- **Measured** (`results/m5_check_v2_*.json` vs `results/m5_cite_v2_*.json`; same generator prompt, and 302/303 `dev_sample` raw answers are byte-identical, so every difference is the check):

  | | M4 v2 | cite-v2 + check-v1 | **cite-v2 + check-v2** |
  |---|---|---|---|
  | Correct (`dev_sample`) | 0.908 | 0.894 | **0.901** |
  | Correct when answered | 0.939 | 0.928 | 0.938 |
  | Faithful, final answer | 0.986 | 0.980 | 0.986 |
  | False abstention | 0.033 | 0.036 | 0.040 |
  | Citation validity (self-checked) | – | 0.971 | 0.976 |
  | Coverage, final answer | – | 0.929 | 1.000 (by construction) |
  | Sentences removed | – | 0.005 | 0.010 |
  | Sentences (re-)attributed | – | 6 | 60 |
  | Abstention on `abstention_set` | 0.882 | 0.868 | 0.862 |
  | Median end-to-end ms (stitched) | 16,214 | 24,922 | 26,732 |

- **Manual review** (`results/m5_check_v2_report.md`; reviewed by Claude against the passage excerpts, verdicts accepted by me): **new seeded sample (seed 6) 10/10 valid**; three borderline claims were checked against the full passage text and are stated there. **Re-review of the cite-v2 sample still 7/10**: none of the 3 failures was fixed. The two-claim sentence passed the joint check; the loose inference passed again; the uncited contradicting "Yes" was now checked but judged supported and *given* a citation, which makes a wrong claim look grounded. The inheritance answer (from outside knowledge, refused by check-v1) now passes too. On the other side, check-v2 removed 2 wrong answers on `dev_sample` that check-v1 had kept.
- **Why keep check-v2:** structurally it asks the right questions (all sentences checked, claims judged against their passages jointly), it matches or beats check-v1 on every answer metric except false abstention (+0.004, 1 question), and the fresh review sample is clean. **Known limitation:** the remaining errors are the qwen3:8b checker being lenient, so self-checked validity (0.976) overstates real validity; across the 20 reviewed answers, 17 were valid. The next lever is the checker model, not more policy code.

## M6 — Scale, API and ship

### D36. Full-corpus index: one `full` collection, section-less distractors kept, M1-M5 pinned to `dev_slice`
- **Chosen:** `scripts/ingest.py --split full` builds a second Qdrant collection, `full` (980 papers = 1,000 minus the 20 `held_out`; 60,153 chunks). `[retrieve] collection` now defaults to `full`; `eval.runners.run` and `eval.runners.ablation` take `--collection dev_slice` to reproduce M1-M5, and `scripts/m2_gate.py` pins it. 3 distractors whose Vectara corpus doc has an empty `sections` list (DATA.md) are indexed under section `-1` rather than skipped. They have no questions, so no metric depends on their section id, and they still do their job as retrieval noise.
- **Alternatives:** skip the 3 papers (corpus becomes 977 papers, no longer the published one); split sections ourselves from PDF headings (reintroduces the heading detection D12 avoided, for 3 papers with no qrels).
- **Measured** (`results/m6_index.txt`): 980/980 papers indexed, 0 `held_out` papers, 60,153/60,153 chunks carry paper id, section id and page, no duplicate (paper, chunk). 2,187/2,189 gold sections of the `full` split map to a chunk; the 2 unmapped ones cover 3/2,893 questions (0.1%), a hard ceiling listed in the file.

### D37. Embedded Qdrant at 60k points, and an API that serves one query at a time
- **Chosen:** keep embedded (local-mode) Qdrant for the full index, despite qdrant-client's warning above 20,000 points. Dense search is a brute-force scan in local mode, but first-stage retrieval (dense + BM25 + RRF) measured 267-808 ms per query after warm-up on the first 10 `full`-index queries, against a 24 s median end-to-end. The LLM calls dominate, so a Qdrant server would buy nothing measurable here. The FastAPI app holds one graph and serialises `/query` with a lock: the LLM, reranker and embedded Qdrant share one 6 GB GPU and one process.
- **Alternatives:** a Qdrant server in Docker (needed for multi-process serving or a much larger corpus; it is the first step of the cloud-deployment backlog item); async/concurrent request handling (requests would just queue on the GPU).
- **Why:** no new infrastructure for a latency that is <4% of a query. Revisit when the API serves more than one user.

### D38. Final configuration on the full corpus, and why it scores lower than on the dev sample
- **Chosen:** the M5 pipeline (`m5_check_v2`: hybrid + rerank, corrective loop, cite-v2 + check-v2), unchanged, on the 980-paper `full` index, run on `dev_sample`, `abstention_set` and all 2,893 `full` questions (`results/m6_graph_*.json`). No retuning on `full`: it is the held-back test of choices made on `dev_sample`.
- **Measured** (`results/m6_graph_full.json`, `results/m6_report.md`):

  | | Dev index, `dev_sample` | Full index, `dev_sample` | Full index, `full` |
  |---|---|---|---|
  | R@5 | 0.937 | 0.927 | 0.917 |
  | Correct | 0.901 | 0.898 | 0.841 |
  | Correct, text | 0.941 | 0.931 | 0.907 |
  | Abstention on `abstention_set` | 0.862 | 0.776 | – |

  `full` also: faithful 0.979, false abstention 0.061, citation validity 0.981, 0 queries over the retry limit, median 28.7 s/question. 4 judge errors (2 correctness verdicts missing, n=2,891).
- **Why it drops:** index size costs little (same questions: R@5 −0.010, Correct −0.003). The `full` drop is the question set: within the one full run, the other 2,590 questions score 0.835 Correct vs 0.894 for `dev_sample`, with nearly equal R@5 (0.915 vs 0.927), so the gap is in answering (correct-if-answered 0.892 vs 0.934), refusals (0.063 vs 0.043) and text-image questions (0.699 vs 0.806). `dev_sample` was the tuning set for every prompt and threshold, so it is optimistic. Of 427 wrong answers there, 216 had gold in the top-5, 164 were refusals, 47 were retrieval misses: the next lever is the LLM, not retrieval.
- **Abstention drop** (0.862 → 0.776, 21 → 34 answered): with 10× the distractors, the grader finds near-miss passages more often. 17/34 answers had an official distractor as the top passage, and 24/34 were graded sufficient at the first attempt. Not hand-checked; some may be genuinely answerable from another paper (the CLAUDE.md caveat).

### D39. Judge calibration: 50 blind human labels, qwen3:8b vs llama3.1:8b, Cohen's kappa
- **Chosen:** a seeded sample (`[calibration]`, seed 20261023) of 25 faithfulness and 25 correctness verdict inputs from the M6 headline runs, labeled by me **blind** (`eval/calibration/m7_sheet.md` shows no judge output, unlike the M2 sample in D20, which showed the judge's verdict and reason). Each judge gets the identical prompts (`judge-v1`) and inputs the M6 eval judge saw. Agreement with my labels is reported as raw agreement and Cohen's kappa, per verdict kind (`eval/metrics/agreement.py`, `eval/runners/calibrate.py`).
- **Second judge:** `llama3.1:8b` on the local Ollama (`[judges.llama]`), the same decoding as the qwen judge (temperature 0, fixed seed, JSON-schema-constrained `{reason, verdict}`), so the comparison is between models. A different model family (Meta vs Alibaba) removes self-preference (D18). Local means free, deterministic, and no quota: the re-score of the M6 runs (~6,600 verdicts) is feasible. Cost: a weaker judge than a hosted frontier model, which kappa against my labels shows directly.
- **Hosted judges tried first, and why they were dropped:**
  - *Gemini 2.5 Flash* (the planned judge): free tier is 20 requests/day (the API's quota error, after 19 of the 50 verdicts). The re-score would need billing.
  - *Gemma 4 31B* over the same API (Gemma 3 27B is no longer served): persistent transient 500/503 errors outlasted ~3 min of retries; 6 of 50 verdicts after four resumed runs, 40-110 s per successful call. The re-score would take days.
  - The client support stays (`halo/llm.py: gemini_chat`, paced by `[gemini] min_interval_seconds`, its own `http_retries`), so a paid hosted judge is a config change. The partial hosted verdicts are not used.
- **Sampling:** negatives (by qwen's saved verdict) oversampled to up to 40% per kind, because raw rates are ~97% supported / ~94% correct and kappa on a near-constant sample is meaningless. Faithfulness draws from `m6_graph_dev_sample` *and* the answered `m6_graph_abstention_set` questions: `dev_sample` has only 3 "unsupported" verdicts out of 290, so all 8 qwen negatives were taken (17 dev + 8 abstention-set items). Consequence: sample agreement is not the population agreement; kappa is the statistic reported, and the stratification is stated next to it.
- **Alternatives:** label the 10-item M2 sample (non-blind, wrong pipeline); a Claude Haiku judge or paid Gemini 2.5 Flash (stronger, different families, but need billing at this volume); RAGAS-style metrics (would add a framework and another judge to calibrate).
- **Results** (`results/m7_judge_calibration.md`, n = 25 per kind; I labeled 10 faithfulness and 7 correctness items negative):

  | Kind | qwen3:8b agreement / κ | llama3.1:8b agreement / κ |
  |---|---|---|
  | faithfulness | 0.76 / 0.48 | 0.64 / 0.12 |
  | correctness | 0.80 / 0.56 | 0.80 / 0.48 |

- **Chosen judge: qwen3:8b, unchanged.** It has the higher κ on both kinds. llama3.1:8b is unusable for faithfulness: it said "supported" on 24 of 25 items, including 9 I labeled unsupported. Self-preference is therefore not the dominant error at this model size; judge capability is.
- **Consequence for reported numbers:** none move. Re-judging with the chosen judge reproduces the saved M6 verdicts (50 of 50 identical, deterministic decoding), so the M6 results stand as the qwen-judged numbers. What changes is how they are read: the qwen confusion counts say Faithful is overstated (4 of the 17 sampled "supported" answers were unsupported to me) and Correct is understated (4 of the 10 sampled "incorrect" answers were correct to me, 1 of 15 "correct" was not). The sample is stratified, so these are direction and rough size, not corrected population rates. Stated in README limitations.
- **Next lever, not done:** a stricter faithfulness prompt (`judge-v2`) calibrated on these labels, or a paid hosted judge (config change).

### D40. CI regression gate: a committed results file, checked for staleness, on R@5 and MRR
- **Chosen:** GitHub Actions on `ubuntu-latest` runs `ruff check` → `pytest` → `python -m eval.runners.ci check`. The gate does not run retrieval. It checks `results/ci_retrieval_dev_sample.json`, which `eval.runners.ci run` writes locally (retrieval-only, configured method and collection, `dev_sample`, ~5 min on the RTX 4050), against the committed baseline `results/m8_ci_baseline.json`. It fails when:
  1. the file is **stale**: produced from a dirty tree, from a commit that is not an ancestor of the PR head, or any `[ci] watch` path (`halo`, `config`, `splits`, `eval/metrics`, `eval/runners`, `eval/results.py`, `pyproject.toml`, `uv.lock`) changed between that commit and the PR head; or its stored config differs from `config/default.toml` at HEAD;
  2. its summary does not match its per-query rankings (R@5 and MRR are recomputed from `per_query`, so a hand-edited mean fails);
  3. R@5 or MRR is more than `[ci] max_drop` below the baseline.

  A literal "results `git_commit` == PR head" check is impossible (a commit cannot contain its own hash), so the rule is "nothing that affects retrieval changed since the results commit". Workflow: commit code → `ci run` → commit the results file → push. CI checks out the PR head, not the merge commit, so a moving `main` does not mark a branch stale.
- **Alternatives:**
  - *(a) Self-hosted runner on this machine*: runs the real gate, but the repo is public, and GitHub advises against self-hosted runners on public repos because a fork's PR can execute code on the host.
  - *(c) Small cached fixture index*: runs on a hosted runner, but the reranker (bge-reranker-v2-m3, 2.2 GB) on CPU measured 39.7 s/query (D29), dense retrieval still needs query embeddings from Ollama, and the metric would be a fixture's, not `dev_sample`'s.
- **Limitation:** (b) rests on trust. The per-query records themselves could be forged; the gate only proves the file is consistent and current. Acceptable for a single-author repo; a self-hosted runner on a private repo would close it.
- **Metrics:** R@5 and MRR only. They are deterministic (two consecutive runs at `02e4133`: 0 of 303 queries with a different top-10, identical metrics) and cheap. LLM metrics stay out of CI: non-deterministic across Ollama versions, ~30 s/question, and need the judge.
- **Baseline** (`results/m8_ci_baseline.json`, commit `02e4133`, hybrid_rerank on the `full` index, n = 303): **R@5 0.9373, MRR 0.8154**, retrieval median 1.03 s/query. These equal the M6 graph's first-attempt metrics exactly (`first_recall@5` 0.9373, `first_mrr` 0.8154 in `results/m6_graph_dev_sample.json`), so the gate measures stage 1 of the shipped pipeline. The graph's headline R@5 0.927 (D38) is lower because it scores the final attempt's hits, after any rewrites.
- **Threshold:** `max_drop = 0.005` absolute for both. One query out of 303 moves R@5 by 0.0033, so the gate tolerates one flipped query and nothing more. Since retrieval is deterministic, any drop is a real change; the tolerance only absorbs a single tie-break flip if a dependency upgrade perturbs reranker scores. A deliberate improvement passes, and the baseline is raised by re-running with `--update-baseline`.
- **CI environment:** Linux resolves torch from the PyTorch CPU index (`[tool.uv.sources]` marker), so the runner does not download ~3 GB of CUDA libraries; the Windows lock entry (`2.11.0+cu128`) is unchanged. Ruff's rule set is pinned (`E4, E7, E9, F, I`) so a ruff upgrade cannot change what CI enforces; bugbear was left out because its `zip(strict=)` fixes would change indexing code.
