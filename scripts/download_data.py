"""Download the official Open RAG Bench release: HF metadata, Vectara's parsed corpus, and arXiv PDFs.

Idempotent: existing valid files are skipped, writes are atomic (.part then rename),
so an interrupted run can simply be restarted.

    uv run python scripts/download_data.py
"""

import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from halo.config import load_config
from halo.data import HF_FILES, corpus_dir, hf_dir, load_hf, pdf_dir

USER_AGENT = "halo-research-bot/0.1 (portfolio RAG benchmark; contact: repo owner)"
HF_WORKERS = 8  # HF CDN handles parallel requests fine; arXiv does not (sequential below).


def fetch(url: str, dest: Path, timeout: int, retries: int, validate=None) -> bool:
    """Download url to dest atomically. Returns True if a download happened."""
    if dest.exists() and (validate is None or validate(dest)):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                tmp.write_bytes(resp.read())
            if validate and not validate(tmp):
                raise ValueError(f"downloaded file failed validation: {url}")
            tmp.replace(dest)
            return True
        except Exception as exc:  # network errors, HTTP errors, validation
            if attempt == retries:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(f"failed after {retries} attempts: {url}") from exc
            time.sleep(2**attempt)
    return False


def is_pdf(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(5) == b"%PDF-"


def main() -> None:
    cfg = load_config()
    d = cfg["data"]
    timeout, retries = d["http_timeout_seconds"], d["http_retries"]
    base = d["hf_base_url"]

    for name in HF_FILES:
        fetch(f"{base}/{name}", hf_dir(cfg) / name, timeout, retries)
    print(f"HF metadata: {len(HF_FILES)} files in {hf_dir(cfg)}")

    pdf_urls = load_hf("pdf_urls.json", cfg)
    doc_ids = sorted(pdf_urls)

    def get_corpus(doc_id: str) -> bool:
        return fetch(f"{base}/corpus/{doc_id}.json", corpus_dir(cfg) / f"{doc_id}.json", timeout, retries)

    with ThreadPoolExecutor(HF_WORKERS) as pool:
        new = sum(pool.map(get_corpus, doc_ids))
    print(f"Corpus JSON: {len(doc_ids)} docs ({new} downloaded now)")

    failed, new = [], 0
    for i, doc_id in enumerate(doc_ids, 1):
        try:
            if fetch(pdf_urls[doc_id], pdf_dir(cfg) / f"{doc_id}.pdf", timeout, retries, validate=is_pdf):
                new += 1
                print(f"  [{i}/{len(doc_ids)}] {doc_id}", flush=True)
                time.sleep(d["arxiv_delay_seconds"])
        except RuntimeError as exc:
            failed.append(doc_id)
            print(f"  FAILED {doc_id}: {exc.__cause__}", flush=True)
    print(f"PDFs: {len(doc_ids) - len(failed)}/{len(doc_ids)} present ({new} downloaded now)")
    if failed:
        raise SystemExit(f"{len(failed)} PDFs failed; re-run to retry: {failed}")


if __name__ == "__main__":
    main()
