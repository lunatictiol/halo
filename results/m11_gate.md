# M11 gate: Docker

Design and decisions: DECISIONS.md D44. Files: `Dockerfile`, `docker-compose.yml`, `docker-compose.gpu.yml`, `docker/entrypoint.sh`, `scripts/pull_models.py`, `scripts/m11_gate.py`, `halo/api/ready.py`. Measurements: [`m11_docker.json`](m11_docker.json), made by `scripts/m11_gate.py --gpu` at commit `641be55` from a clean tree.

Machine: Windows 11, Docker Desktop 29.7.2 (WSL2, containerd image store), one NVIDIA RTX 4050 Laptop GPU (6 GB). Everything below was run once, on this machine. The console outputs in the tables were copied from the runs; only `m11_docker.json` is a script-written file.

## Gate

- [x] **On a clean checkout, `docker compose up` plus the documented index step serves the M10 frontend and answers a query end-to-end** (with the exceptions listed under the table).

  | Check | Result |
  |---|---|
  | GPU stack on the real full index (`./data`, 980 papers, 60,153 chunks), driven by `scripts/m11_gate.py` | `/ready` 200; `GET /` 200 with the question form; the three demo questions streamed over HTTP with no errors: direct (0 retries), rescued (1 retry), abstention (2 retries, abstained). Numbers in `m11_docker.json` |
  | Documented index step in a container, empty data directory: `docker compose run --rm app python scripts/ingest.py --split dev_slice` | exit 0, 103 papers, wall 530 s, index 60 MB. Chunk count 6,740, equal to the natively built `dev_slice` collection (6,740) |
  | Serve that index: `HALO_COLLECTION=dev_slice docker compose up -d app` | `/ready` 200 after 11 s; `/health` reports `"collection":"dev_slice"`; `POST /query` for "What is the correlation between the tax instrument and recovered tax shock during the Great Moderation?" returned an answer ending `[2403.08753v2 §11 p.28]` with 1 citation, 0 retries |
  | No index: `docker compose run --rm app` on a data directory with none | exit code 3; `RuntimeError: index collection 'full' not found: build it first (README, Docker quickstart)` |
  | `download_data.py` in a container, empty directory, stopped by `timeout 90` | 4 HF metadata files and 421 corpus JSON files written into the mounted volume; exit 124 (stopped by the timeout, as intended) |
  | First start with an empty Hugging Face cache | the entrypoint downloaded the reranker (33 files, 2,187 MB) and the command's second run of `pull_models.py` printed `already present`: 377 s for both. A third container loaded `BAAI/bge-reranker-v2-m3` with `HF_HUB_OFFLINE=1` and scored a test pair (0.992), so the cached files are sufficient offline |

  **Exceptions, stated plainly.** It was not a literal fresh `git clone`: the build context was this working tree filtered by `.dockerignore`, and a clean data state was simulated with scratch data directories. The one-hour PDF download and the full 980-paper ingest were not re-run in a container: the full index was built natively earlier and is the one mounted in the first row. The index step was exercised end to end on `dev_slice` only.

- [x] **README quickstart has a Docker path next to the uv path; image size and cold-start time recorded.** README "Quickstart"; sizes and cold start are in `m11_docker.json` and the README's Docker results table.

## Other checks

- `uv run pytest`: 129 passed. `uv run ruff check .`: clean.
- CI regression gate after the M11 code commit (`28dcc6f`): R@5 0.9373, MRR 0.8154, delta +0.0000 against `m8_ci_baseline`; `eval.runners.ci check` passes. Retrieval is unchanged; the refreshed results are committed as `641be55`.
- All 8 Mermaid diagrams in the README parse with Mermaid 11.
- Independent code review (a read-only agent on the uncommitted diff): no CRITICAL or HIGH findings. Five MEDIUM findings were verified against the code and fixed: the reranker was downloaded lazily on the first query (now fetched by the entrypoint), `dev_slice` could not be served (now `HALO_COLLECTION`), the Linux bind-mount owner (now `HALO_UID`/`HALO_GID`), the results file recording the host's config instead of the container's (now `container_env`), and test gaps (startup index check, pull streaming, reranker prefetch). LOW findings fixed: the pull stream now needs a final `success`, the Ollama probe timeout moved into config, `.dockerignore` covers nested `.env*` files. LOW findings deliberately not changed: the unpinned `ollama/ollama:latest` image and the hand-pinned CUDA `torch` (documented in D44), and `/ready` echoing the Ollama URL (acceptable behind the loopback-only port).

## Not exercised

The CPU image answering a query (it was built, not run); a Linux host or the NVIDIA Container Toolkit; macOS; a literal fresh clone; the PDF phase of `download_data.py` in a container.
