"""M5 citations and grounding check (DECISIONS.md D31-D33).

The generator cites passages by number ("... 4 layers [2]."). Code, not the model, turns [n] into
(paper, section, page) from the chunk's metadata, so a citation can only point at a passage that was retrieved.
The grounding check asks the LLM, per (sentence, cited passage) pair, whether the passage supports the sentence:
  - a sentence with >= 1 supported citation is kept, with its unsupported citations stripped;
  - a cited sentence with no supported citation is removed;
  - an uncited sentence is kept but flagged (it lowers citation coverage);
  - no grounded sentence left -> abstain.
"""

import re
from collections.abc import Callable

from halo.generate.baseline import format_context
from halo.llm import chat, classify

CHECK = ("supported", "unsupported")
_MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_MARKERS = r"(?:\s*\[\d+(?:\s*,\s*\d+)*\])+"
# "... sentence. [1]" -> "... sentence [1]." so the marker stays with the sentence it follows.
_TRAILING = re.compile(rf"([.!?])({_MARKERS})(?=\s|$)")
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
# A period after these does not end a sentence (common in research-paper prose).
_ABBREV = re.compile(r"(?:\b(?:e\.g|i\.e|et al|cf|vs|Fig|Figs|Eq|Eqs|Sec|Tab|Ref|approx|resp|No)\.|\b[A-Z]\.)$")

# check(sentence, chunk) -> {verdict, reason, ms}
Check = Callable[[str, dict], dict]


def cite_answer(question: str, chunks: list[dict], cfg: dict) -> dict:
    c, g = cfg["cite"], cfg["generate"]
    user = g["user_prompt"].format(context=format_context(chunks), question=question)
    return chat(c["system_prompt"].format(sentinel=g["sentinel"]), user, cfg["models"]["llm"], g["max_tokens"], cfg)


def _move_marker(m: re.Match) -> str:
    if _ABBREV.search(m.string[:m.end(1)]):  # "et al. [1]" is not a sentence end
        return m.group(0)
    return m.group(2) + m.group(1)


def split_sentences(text: str) -> list[str]:
    text = _TRAILING.sub(_move_marker, " ".join(text.split()))
    out: list[str] = []
    for piece in _BOUNDARY.split(text):
        if out and _ABBREV.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return [s for s in out if s.strip()]


def parse_sentence(sentence: str) -> tuple[str, list[int]]:
    """Text without markers, and the cited passage numbers in order of first appearance."""
    ids = [int(n) for m in _MARKER.finditer(sentence) for n in m.group(1).split(",")]
    text = re.sub(r"\s+([.!?,;:])", r"\1", _MARKER.sub("", sentence)).strip()
    return " ".join(text.split()), list(dict.fromkeys(ids))


def label(chunk: dict) -> str:
    return f"[{chunk['paper_id']} §{chunk['section_id']} p.{chunk['page']}]"


def _render(text: str, cites: list[dict]) -> str:
    if not cites:
        return text
    tags = " ".join(c["label"] for c in cites)
    return f"{text[:-1]} {tags}{text[-1]}" if text[-1:] in ".!?" else f"{text} {tags}"


def ground(answer: str, chunks: list[dict], check: Check) -> dict:
    """Split, resolve and check every citation of an answer; returns the per-sentence record and final text.
    A citation number outside 1..len(chunks) is invalid without an LLM call. A checker parse failure
    (verdict None) does not keep a sentence (same rule as the grader) and is excluded from validity."""
    sentences, cache = [], {}
    for raw in split_sentences(answer):
        text, ids = parse_sentence(raw)
        if not text:
            continue
        cites = []
        for n in ids:
            if not 1 <= n <= len(chunks):
                cites.append({"n": n, "label": "[?]", "verdict": "out_of_range", "reason": None})
                continue
            ch = chunks[n - 1]
            if (text, n) not in cache:
                cache[text, n] = check(text, ch)
            v = cache[text, n]
            cites.append({"n": n, "label": label(ch), "paper_id": ch["paper_id"], "section_id": ch["section_id"],
                          "page": ch["page"], "verdict": v["verdict"], "reason": v["reason"]})
        supported = [c for c in cites if c["verdict"] == "supported"]
        sentences.append({"text": text, "cites": cites, "grounded": bool(supported) if cites else None,
                          "kept": bool(supported) or not cites, "final": _render(text, supported)})
    kept = [s for s in sentences if s["kept"]]
    return {"sentences": sentences,
            "raw": " ".join(_render(s["text"], s["cites"]) for s in sentences),
            "final": " ".join(s["final"] for s in kept),
            "abstained": not any(s["grounded"] for s in kept)}


def llm_check(question: str, cfg: dict) -> Check:
    c = cfg["cite"]

    def check(sentence: str, chunk: dict) -> dict:
        prompt = c["check_prompt"].format(question=question, claim=sentence, passage=format_context([chunk]))
        return classify(c["check_system_prompt"], prompt, CHECK, cfg["models"]["llm"], c["check_max_tokens"],
                        c["check_parse_retries"], cfg)
    return check
