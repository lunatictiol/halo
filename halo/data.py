"""Paths and loaders for the Open RAG Bench files (formats documented in DATA.md)."""

import hashlib
import json
from pathlib import Path

from halo.config import ROOT, load_config

HF_FILES = ("queries.json", "answers.json", "qrels.json", "pdf_urls.json")


def data_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    return ROOT / cfg["data"]["data_dir"]


def hf_dir(cfg: dict | None = None) -> Path:
    return data_dir(cfg) / "hf"


def corpus_dir(cfg: dict | None = None) -> Path:
    return hf_dir(cfg) / "corpus"


def pdf_dir(cfg: dict | None = None) -> Path:
    return data_dir(cfg) / "pdfs"


def load_hf(name: str, cfg: dict | None = None) -> dict:
    """Load one of HF_FILES, e.g. load_hf('qrels.json')."""
    return json.loads((hf_dir(cfg) / name).read_text(encoding="utf-8"))


def load_corpus_doc(doc_id: str, cfg: dict | None = None) -> dict:
    return json.loads((corpus_dir(cfg) / f"{doc_id}.json").read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_split(name: str) -> dict:
    """A committed split file (splits/<name>.json): {name, seed, inputs_sha256, paper_ids, query_ids}."""
    return json.loads((ROOT / "splits" / f"{name}.json").read_text(encoding="utf-8"))
