"""M5 citations and grounding check (DECISIONS.md D31-D34).

The generator cites passages by label ("... 4 layers [P2]."). Labels are P-prefixed because chunk text is full of
the papers' own bibliography markers ("[21]"), which cite-v1's plain numbers collided with (D34). Code, not the
model, turns [Pn] into (paper, section, page) from the chunk's metadata, so a citation can only point at a passage
that was retrieved. The grounding check (D35) asks the LLM, once per sentence, whether its cited passages together
support everything the sentence says (per-passage checks let one passage carry a second, unsupported claim):
  - supported -> kept with its citations;
  - otherwise, and for uncited sentences, each other passage is tried alone and the sentence is (re-)attributed to
    the first one that supports it (the right text is often in the neighbouring chunk); otherwise it is removed;
  - no sentence left -> abstain.
"""

import re
from collections.abc import Callable

from halo.generate.baseline import format_context
from halo.llm import chat, classify

CHECK = ("supported", "unsupported")
_MARKER = re.compile(r"\[(P\d+(?:\s*,\s*P?\d+)*)\]", re.IGNORECASE)
_MARKERS = r"(?:\s*\[[Pp]\d+(?:\s*,\s*[Pp]?\d+)*\])+"
# Bibliography markers copied from passage text ("[21]", "[3, 8]", "[4-6]") are not citations; they are dropped.
_BIB = re.compile(r"\s*\[\d+(?:\s*[,–-]\s*\d+)*\]")
# "... sentence. [P1]" -> "... sentence [P1]." so the marker stays with the sentence it follows.
_TRAILING = re.compile(rf"([.!?])({_MARKERS})(?=\s|$)")
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
# A period after these does not end a sentence (common in research-paper prose).
_ABBREV = re.compile(r"(?:\b(?:e\.g|i\.e|et al|cf|vs|Fig|Figs|Eq|Eqs|Sec|Tab|Ref|approx|resp|No)\.|\b[A-Z]\.)$")

# check(sentence, chunks) -> {verdict, reason, ms}: do these passages together support the sentence?
Check = Callable[[str, list[dict]], dict]


def format_cite_context(chunks: list[dict]) -> str:
    """format_context with P-labels: [P1] (paper ..., section ...: title, page ...)."""
    return "\n\n".join(f"[P{i}] {format_context([c]).split('] ', 1)[1]}" for i, c in enumerate(chunks, 1))


def cite_answer(question: str, chunks: list[dict], cfg: dict) -> dict:
    c, g = cfg["cite"], cfg["generate"]
    user = g["user_prompt"].format(context=format_cite_context(chunks), question=question)
    return chat(c["system_prompt"].format(sentinel=g["sentinel"]), user, cfg["models"]["llm"], g["max_tokens"], cfg)


def _move_marker(m: re.Match) -> str:
    if _ABBREV.search(m.string[:m.end(1)]):  # "et al. [P1]" is not a sentence end
        return m.group(0)
    return m.group(2) + m.group(1)


def split_sentences(text: str) -> list[str]:
    text = _TRAILING.sub(_move_marker, _BIB.sub("", " ".join(text.split())))
    out: list[str] = []
    for piece in _BOUNDARY.split(text):
        if out and _ABBREV.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return [s for s in out if s.strip()]


def parse_sentence(sentence: str) -> tuple[str, list[int]]:
    """Text without citation or bibliography markers, and the cited passage numbers in order of first appearance."""
    ids = [int(n.strip().lstrip("Pp")) for m in _MARKER.finditer(sentence) for n in m.group(1).split(",")]
    text = re.sub(r"\s+([.!?,;:])", r"\1", _BIB.sub("", _MARKER.sub("", sentence))).strip()
    return " ".join(text.split()), list(dict.fromkeys(ids))


def label(chunk: dict) -> str:
    return f"[{chunk['paper_id']} §{chunk['section_id']} p.{chunk['page']}]"


def _render(text: str, cites: list[dict]) -> str:
    if not cites:
        return text
    tags = " ".join(c["label"] for c in cites)
    return f"{text[:-1]} {tags}{text[-1]}" if text[-1:] in ".!?" else f"{text} {tags}"


def ground(answer: str, chunks: list[dict], check: Check) -> dict:
    """Split, resolve and check every sentence of an answer; returns the per-sentence record and final text.
    `cites` are the generator's own citations, each carrying its sentence's joint verdict (what validity
    measures); `reattributed` is the passage the check moved a failed or uncited sentence to, if any. A citation
    number outside 1..len(chunks) is invalid without an LLM call. A checker parse failure (verdict None) does not
    keep a sentence (same rule as the grader) and is excluded from validity."""
    cache = {}

    def verdict(text: str, ns: tuple[int, ...]) -> dict:
        if (text, ns) not in cache:
            cache[text, ns] = check(text, [chunks[n - 1] for n in ns])
        return cache[text, ns]

    def ref(n: int, v: dict) -> dict:
        ch = chunks[n - 1]
        return {"n": n, "label": label(ch), "paper_id": ch["paper_id"], "section_id": ch["section_id"],
                "page": ch["page"], "verdict": v["verdict"], "reason": v["reason"]}

    sentences = []
    for raw in split_sentences(answer):
        text, ids = parse_sentence(raw)
        if not text:
            continue
        valid = tuple(n for n in ids if 1 <= n <= len(chunks))
        v = verdict(text, valid) if valid else None
        cites = [ref(n, v) if n in valid else {"n": n, "label": "[?]", "verdict": "out_of_range", "reason": None}
                 for n in ids]
        supported, moved = [c for c in cites if c["verdict"] == "supported"], None
        if not supported:  # failed or uncited: (re-)attribute to the first single other passage that supports it
            others = (ref(n, verdict(text, (n,))) for n in range(1, len(chunks) + 1) if n not in valid)
            moved = next((c for c in others if c["verdict"] == "supported"), None)
            supported = [moved] if moved else []
        sentences.append({"text": text, "cites": cites, "reattributed": moved, "grounded": bool(supported),
                          "kept": bool(supported), "final": _render(text, supported)})
    kept = [s for s in sentences if s["kept"]]
    return {"sentences": sentences,
            "raw": " ".join(_render(s["text"], s["cites"]) for s in sentences),
            "final": " ".join(s["final"] for s in kept),
            "abstained": not kept}


def llm_check(question: str, cfg: dict) -> Check:
    c = cfg["cite"]

    def check(sentence: str, chunks: list[dict]) -> dict:
        prompt = c["check_prompt"].format(question=question, claim=sentence, passages=format_context(chunks))
        return classify(c["check_system_prompt"], prompt, CHECK, cfg["models"]["llm"], c["check_max_tokens"],
                        c["check_parse_retries"], cfg)
    return check
