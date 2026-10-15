"""Minimal Ollama chat client shared by generation and the eval judge. Deterministic settings from [llm]."""

import json
import time
import urllib.error
import urllib.request


class ContextOverflow(RuntimeError):
    """The prompt filled the context window, so Ollama may have silently truncated it."""


def _post(req: urllib.request.Request, llm: dict) -> dict:
    """POST with bounded retries on server-side failures (Ollama returns 500 transiently while swapping
    models in and out of the 6 GB of VRAM). Client errors (4xx) are bugs and raise immediately."""
    for attempt in range(llm["http_retries"] + 1):
        try:
            with urllib.request.urlopen(req, timeout=llm["timeout_seconds"]) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == llm["http_retries"]:
                raise
        except urllib.error.URLError:
            if attempt == llm["http_retries"]:
                raise
        time.sleep(llm["retry_backoff_seconds"] * (attempt + 1))
    raise AssertionError("unreachable")


def chat(system: str, user: str, model: str, max_tokens: int, cfg: dict, schema: dict | None = None) -> dict:
    """One non-streaming chat call. Returns content, token counts and wall-clock latency."""
    llm = cfg["llm"]
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "think": llm["think"],
        "options": {"temperature": llm["temperature"], "seed": llm["seed"],
                    "num_ctx": llm["num_ctx"], "num_predict": max_tokens},
    }
    if schema is not None:
        body["format"] = schema
    req = urllib.request.Request(f"{cfg['models']['ollama_url']}/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    start = time.perf_counter()
    resp = _post(req, llm)
    ms = round((time.perf_counter() - start) * 1000)
    prompt_tokens, output_tokens = resp.get("prompt_eval_count", 0), resp.get("eval_count", 0)
    if prompt_tokens + output_tokens >= llm["num_ctx"]:
        raise ContextOverflow(f"{prompt_tokens}+{output_tokens} tokens >= num_ctx {llm['num_ctx']}")
    return {"content": resp["message"]["content"].strip(), "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens, "ms": ms}
