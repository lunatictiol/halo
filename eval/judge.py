"""LLM judge for faithfulness (answer vs retrieved context) and correctness (answer vs reference).

Verdicts are binary labels plus a one-sentence reason, requested as schema-constrained JSON with the
reason first so the model states its evidence before committing to a label (DECISIONS.md D18).
"""

import json
import re

from halo.generate.baseline import format_context
from halo.llm import chat

FAITHFULNESS = ("supported", "unsupported")
CORRECTNESS = ("correct", "incorrect")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class JudgeParseError(ValueError):
    pass


def _schema(allowed: tuple[str, ...]) -> dict:
    return {"type": "object", "required": ["reason", "verdict"],
            "properties": {"reason": {"type": "string"}, "verdict": {"type": "string", "enum": list(allowed)}}}


def parse_verdict(text: str, allowed: tuple[str, ...]) -> tuple[str, str]:
    try:
        obj = json.loads(_FENCE.sub("", text.strip()))
    except json.JSONDecodeError as e:
        raise JudgeParseError(f"not JSON: {text[:80]!r}") from e
    if not isinstance(obj, dict) or not isinstance(obj.get("verdict"), str):
        raise JudgeParseError(f"no verdict field: {text[:80]!r}")
    verdict = obj["verdict"].strip().lower()
    if verdict not in allowed:
        raise JudgeParseError(f"verdict {verdict!r} not in {allowed}")
    return verdict, str(obj.get("reason", "")).strip()


def _judge(prompt: str, allowed: tuple[str, ...], cfg: dict) -> dict:
    """Ask, retrying on unparseable output. A persistent failure is recorded (verdict None), not guessed.
    Decoding is greedy, so a retry only differs by a larger token budget (the likely cause is truncated JSON)."""
    j = cfg["judge"]
    errors = []
    for attempt in range(1 + j["parse_retries"]):
        resp = chat(j["system_prompt"], prompt, j["model"], j["max_tokens"] * (attempt + 1), cfg,
                    schema=_schema(allowed))
        try:
            verdict, reason = parse_verdict(resp["content"], allowed)
            return {"verdict": verdict, "reason": reason, "ms": resp["ms"]}
        except JudgeParseError as e:
            errors.append(str(e))
    return {"verdict": None, "reason": f"judge_error: {errors[-1]}", "ms": None}


def judge_faithfulness(question: str, answer: str, chunks: list[dict], cfg: dict) -> dict:
    prompt = cfg["judge"]["faithfulness_prompt"].format(
        question=question, answer=answer, context=format_context(chunks))
    return _judge(prompt, FAITHFULNESS, cfg)


def judge_correctness(question: str, answer: str, reference: str, cfg: dict) -> dict:
    prompt = cfg["judge"]["correctness_prompt"].format(question=question, answer=answer, reference=reference)
    return _judge(prompt, CORRECTNESS, cfg)
