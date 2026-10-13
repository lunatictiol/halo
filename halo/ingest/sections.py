"""Map PDF blocks to Vectara section IDs by word n-gram overlap, then chunk within sections.

Vectara's sections (qrels ground truth) don't follow the PDF's headings, so we don't detect
headings: each block takes the section that contains most of its word n-grams (DECISIONS.md D12).
"""

import re
from collections import Counter
from itertools import groupby

WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def shingles(ws: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def section_title(text: str) -> str:
    """First markdown heading of a Vectara section, '' if none."""
    return next((line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#")), "")


def map_blocks(blocks: list[str], sections: list[dict], n: int, min_match: float) -> list[dict]:
    """For each block: {"section_id", "score", "inherited"}.

    score = share of the block's n-grams found in its best section. Below min_match (headers,
    references, math-only blocks) the block inherits the previous block's section; leading
    weak blocks (title, authors) inherit the first section.
    """
    index: dict[tuple[str, ...], set[int]] = {}
    for s in sections:
        for sh in shingles(words(s["text"]), n):
            index.setdefault(sh, set()).add(s["section_id"])

    prev = sections[0]["section_id"]
    out = []
    for text in blocks:
        sh = shingles(words(text), n)
        votes = Counter(sid for x in sh for sid in index.get(x, ()))
        if votes:
            # Ties go to the earlier section, so the result never depends on set order.
            sid = max(votes, key=lambda s: (votes[s], -s))
            score = votes[sid] / len(sh)
        else:
            sid, score = None, 0.0
        inherited = score < min_match
        if not inherited:
            prev = sid
        out.append({"section_id": prev, "score": score, "inherited": inherited})
    return out


def chunk_blocks(blocks: list[dict], chunk_words: int, overlap_words: int) -> list[dict]:
    """Group consecutive blocks of one section into word windows; chunks never cross sections.

    blocks: [{"section_id", "page", "text"}] in reading order.
    Returns [{"section_id", "page", "page_end", "text"}]; page = page of the first word.
    """
    step = chunk_words - overlap_words
    chunks = []
    for sid, group in groupby(blocks, key=lambda b: b["section_id"]):
        toks = [(w, b["page"]) for b in group for w in b["text"].split()]
        for start in range(0, max(len(toks) - overlap_words, 1), step):
            window = toks[start:start + chunk_words]
            chunks.append({
                "section_id": sid,
                "page": window[0][1],
                "page_end": window[-1][1],
                "text": " ".join(w for w, _ in window),
            })
    return chunks
