"""LLM judge for faithfulness (answer vs retrieved context) and correctness (answer vs reference).

Verdicts are binary labels plus a one-sentence reason, requested as schema-constrained JSON with the
reason first so the model states its evidence before committing to a label (DECISIONS.md D18).
"""

from halo.generate.baseline import format_context
from halo.llm import VerdictParseError as JudgeParseError  # noqa: F401 (re-exported)
from halo.llm import classify, parse_verdict  # noqa: F401 (parse_verdict re-exported)

FAITHFULNESS = ("supported", "unsupported")
CORRECTNESS = ("correct", "incorrect")


def _judge(prompt: str, allowed: tuple[str, ...], cfg: dict) -> dict:
    j = cfg["judge"]
    return classify(j["system_prompt"], prompt, allowed, j["model"], j["max_tokens"], j["parse_retries"], cfg,
                    j["provider"])


def with_judge(cfg: dict, name: str | None) -> dict:
    """cfg with [judges.<name>] swapped into [judge]; prompts and limits stay shared. None = the default judge."""
    return cfg if name is None else cfg | {"judge": cfg["judge"] | cfg["judges"][name]}


def judge_faithfulness(question: str, answer: str, chunks: list[dict], cfg: dict) -> dict:
    prompt = cfg["judge"]["faithfulness_prompt"].format(
        question=question, answer=answer, context=format_context(chunks))
    return _judge(prompt, FAITHFULNESS, cfg)


def judge_correctness(question: str, answer: str, reference: str, cfg: dict) -> dict:
    prompt = cfg["judge"]["correctness_prompt"].format(question=question, answer=answer, reference=reference)
    return _judge(prompt, CORRECTNESS, cfg)
