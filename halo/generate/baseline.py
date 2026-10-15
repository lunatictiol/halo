"""Naive baseline generation: top-k retrieved chunks -> one LLM answer, or the abstention sentinel."""

from halo.llm import chat


def format_context(chunks: list[dict]) -> str:
    """Numbered passages labelled with paper, section and page (the same view the judge gets)."""
    return "\n\n".join(
        f"[{i}] (paper {c['paper_id']}, section {c['section_id']}: {c['section_title']}, page {c['page']})\n{c['text']}"
        for i, c in enumerate(chunks, 1)
    )


def answer(question: str, chunks: list[dict], cfg: dict) -> dict:
    g = cfg["generate"]
    user = g["user_prompt"].format(context=format_context(chunks), question=question)
    system = g["system_prompt"].format(sentinel=g["sentinel"])
    return chat(system, user, cfg["models"]["llm"], g["max_tokens"], cfg)
