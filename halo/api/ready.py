"""What must hold before the API can answer: the index exists (checked once at startup) and Ollama serves both models
(checked on every /ready call, since Ollama can come and go)."""

import json
import urllib.request


def index_problem(client, collection: str) -> str | None:
    if not client.collection_exists(collection):
        return f"index collection {collection!r} not found: build it first (README, Docker quickstart)"
    if client.count(collection).count == 0:
        return f"index collection {collection!r} is empty: build it first (README, Docker quickstart)"
    return None


def installed_models(cfg: dict) -> set[str]:
    """Names Ollama has locally; "nomic-embed-text" is stored as "nomic-embed-text:latest", so both spellings count.
    Raises OSError / ValueError / KeyError when Ollama is unreachable or answers something unexpected."""
    m = cfg["models"]
    with urllib.request.urlopen(f"{m['ollama_url']}/api/tags", timeout=cfg["api"]["ollama_timeout_s"]) as r:
        have = {x["name"] for x in json.load(r)["models"]}
    return have | {n.removesuffix(":latest") for n in have}


def ollama_problems(cfg: dict) -> list[str]:
    m = cfg["models"]
    try:
        have = installed_models(cfg)
    except (OSError, ValueError, KeyError) as e:
        return [f"ollama unreachable at {m['ollama_url']}: {e}"]
    return [f"model {n!r} not pulled" for n in (m["llm"], m["embedding"]) if n not in have]
