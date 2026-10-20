"""Minimal Ollama chat client shared by generation and the eval judge. Deterministic settings from [llm]."""

import json
import re
import time
import urllib.error
import urllib.request


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class ContextOverflow(RuntimeError):
    """The prompt filled the context window, so Ollama may have silently truncated it."""


class VerdictParseError(ValueError):
    pass


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
                    "num_ctx": llm["num_ctx"], "num_predict": max_tokens}
                   | ({"num_gpu": llm["num_gpu"]} if "num_gpu" in llm else {}),
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


def verdict_schema(allowed: tuple[str, ...]) -> dict:
    """Reason before verdict, so the model states its evidence before committing to a label (DECISIONS.md D18)."""
    return {"type": "object", "required": ["reason", "verdict"],
            "properties": {"reason": {"type": "string"}, "verdict": {"type": "string", "enum": list(allowed)}}}


def parse_verdict(text: str, allowed: tuple[str, ...]) -> tuple[str, str]:
    try:
        obj = json.loads(_FENCE.sub("", text.strip()))
    except json.JSONDecodeError as e:
        raise VerdictParseError(f"not JSON: {text[:80]!r}") from e
    if not isinstance(obj, dict) or not isinstance(obj.get("verdict"), str):
        raise VerdictParseError(f"no verdict field: {text[:80]!r}")
    verdict = obj["verdict"].strip().lower()
    if verdict not in allowed:
        raise VerdictParseError(f"verdict {verdict!r} not in {allowed}")
    return verdict, str(obj.get("reason", "")).strip()


def classify(system: str, prompt: str, allowed: tuple[str, ...], model: str, max_tokens: int, retries: int,
             cfg: dict) -> dict:
    """Schema-constrained label + reason, retrying on unparseable output. A persistent failure is recorded
    (verdict None), not guessed. Decoding is greedy, so a retry only differs by a larger token budget (the
    likely cause is truncated JSON)."""
    errors = []
    for attempt in range(1 + retries):
        resp = chat(system, prompt, model, max_tokens * (attempt + 1), cfg, schema=verdict_schema(allowed))
        try:
            verdict, reason = parse_verdict(resp["content"], allowed)
            return {"verdict": verdict, "reason": reason, "ms": resp["ms"]}
        except VerdictParseError as e:
            errors.append(str(e))
    return {"verdict": None, "reason": f"parse_error: {errors[-1]}", "ms": None}
