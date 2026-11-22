"""Load the TOML config. All tunables live in config/*.toml, never in code."""

import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "default.toml"

# Deployment facts that differ per environment (Docker: Ollama is another container, the GPU may be absent; D44).
# Everything else stays in the TOML so results files keep describing the pipeline.
ENV_OVERRIDES = {
    "HALO_OLLAMA_URL": ("models", "ollama_url"),
    "HALO_RERANK_DEVICE": ("rerank", "device"),
    "HALO_COLLECTION": ("retrieve", "collection"),  # serve a try-out index (`ingest.py --split dev_slice`)
}


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    for var, (section, key) in ENV_OVERRIDES.items():
        if var in os.environ:
            cfg[section][key] = os.environ[var]
    return cfg
