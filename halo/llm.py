"""Minimal Ollama chat client shared by generation and the eval judge. Deterministic settings from [llm].
A Gemini client serves the hosted eval judge (M7, DECISIONS.md D39); generation stays local."""

import json
import os
import re
import time
import urllib.error
import urllib.request

from halo.config import ROOT


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class ContextOverflow(RuntimeError):
    """The prompt filled the context window, so Ollama may have silently truncated it."""


class VerdictParseError(ValueError):
    pass


def _post(req: urllib.request.Request, llm: dict) -> dict:
    """POST with bounded retries on server-side failures (Ollama returns 500 transiently while swapping
    models in and out of the 6 GB of VRAM) and on 429 rate limits (hosted judge). Other 4xx are bugs and raise
    immediately."""
    for attempt in range(llm["http_retries"] + 1):
        try:
            with urllib.request.urlopen(req, timeout=llm["timeout_seconds"]) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or attempt == llm["http_retries"]:
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


def _env(name: str) -> str:
    """Environment first, then the gitignored .env file at the repo root."""
    if name in os.environ:
        return os.environ[name]
    env = ROOT / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.exists() else []:
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip().strip("\"'")
    raise RuntimeError(f"{name} is not set (environment or .env)")


_last_gemini = 0.0


def gemini_chat(system: str, user: str, model: str, max_tokens: int, cfg: dict, schema: dict | None = None) -> dict:
    """Same contract as chat(), against the Gemini REST API. Thinking is off and decoding greedy, matching the
    local judge's settings so the comparison is between models, not decoding setups."""
    global _last_gemini
    llm, g = cfg["llm"], cfg["gemini"]
    # ponytail: process-local pacing, fine for one sequential run; a shared limiter if calls ever go concurrent.
    time.sleep(max(0.0, _last_gemini + g["min_interval_seconds"] - time.monotonic()))
    _last_gemini = time.monotonic()
    gen = {"temperature": llm["temperature"], "seed": llm["seed"], "maxOutputTokens": max_tokens}
    if not model.startswith("gemma"):  # Gemma rejects thinkingConfig (400); with a JSON schema it emits no thoughts
        gen["thinkingConfig"] = {"thinkingBudget": g["thinking_budget"]}
    if schema is not None:
        gen |= {"responseMimeType": "application/json", "responseJsonSchema": schema}  # standard JSON Schema, keys emitted in order
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": gen}
    req = urllib.request.Request(f"{g['url']}/models/{model}:generateContent", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "x-goog-api-key": _env(g["api_key_env"])})
    start = time.perf_counter()
    resp = _post(req, llm)
    ms = round((time.perf_counter() - start) * 1000)
    usage = resp.get("usageMetadata", {})
    parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return {"content": "".join(p.get("text", "") for p in parts if not p.get("thought")).strip(),
            "prompt_tokens": usage.get("promptTokenCount", 0), "output_tokens": usage.get("candidatesTokenCount", 0),
            "ms": ms}


CHAT = {"ollama": chat, "gemini": gemini_chat}


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
             cfg: dict, provider: str = "ollama") -> dict:
    """Schema-constrained label + reason, retrying on unparseable output. A persistent failure is recorded
    (verdict None), not guessed. Decoding is greedy, so a retry only differs by a larger token budget (the
    likely cause is truncated JSON)."""
    errors = []
    for attempt in range(1 + retries):
        resp = CHAT[provider](system, prompt, model, max_tokens * (attempt + 1), cfg,
                              schema=verdict_schema(allowed))
        try:
            verdict, reason = parse_verdict(resp["content"], allowed)
            return {"verdict": verdict, "reason": reason, "ms": resp["ms"]}
        except VerdictParseError as e:
            errors.append(str(e))
    return {"verdict": None, "reason": f"parse_error: {errors[-1]}", "ms": None}
