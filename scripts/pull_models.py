"""Fetch everything the app downloads lazily, so the first query does not stall on it: the Ollama models the config
names and the reranker's weights. Anything already present is skipped without touching the network, and
docker/entrypoint.sh runs this on every container start, so a restart works offline once the first start finished.

    uv run python scripts/pull_models.py
"""

import json
import urllib.request

from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError

from halo.api.ready import installed_models
from halo.config import load_config

# What CrossEncoder loads (config, tokenizer, weights); skips the ONNX and pytorch_model.bin copies in the repo.
RERANKER_FILES = ["*.json", "*.model", "*.safetensors"]


def pull(url: str, name: str) -> None:
    req = urllib.request.Request(f"{url}/api/pull", json.dumps({"model": name}).encode(),
                                 {"Content-Type": "application/json"})
    last = None
    with urllib.request.urlopen(req) as r:  # no timeout: a first pull is several GB
        for line in r:
            msg = json.loads(line)
            if "error" in msg:
                raise SystemExit(f"pulling {name} failed: {msg['error']}")
            status = msg.get("status")
            if status != last:
                print(f"{name}: {status}", flush=True)
                last = status
    if last != "success":  # a stream that just stops would otherwise leave the model missing, silently
        raise SystemExit(f"pulling {name} ended without success (last status: {last})")


def fetch_reranker(name: str) -> None:
    try:
        snapshot_download(name, allow_patterns=RERANKER_FILES, local_files_only=True)
        print(f"{name}: already present", flush=True)
    except LocalEntryNotFoundError:
        print(f"{name}: downloading", flush=True)
        snapshot_download(name, allow_patterns=RERANKER_FILES)


def main() -> None:
    cfg = load_config()
    m, have = cfg["models"], installed_models(cfg)
    for name in (m["llm"], m["embedding"]):
        if name in have:
            print(f"{name}: already present", flush=True)
        else:
            pull(m["ollama_url"], name)
    fetch_reranker(cfg["rerank"]["model"])


if __name__ == "__main__":
    main()
