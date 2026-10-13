"""PDF -> text blocks with page numbers (PyMuPDF, text only)."""

from pathlib import Path

import pymupdf

# Dehyphenate line breaks and expand ligatures (no TEXT_PRESERVE_LIGATURES) so PDF words match
# the plain words in Vectara's markdown sections.
TEXT_FLAGS = pymupdf.TEXT_DEHYPHENATE | pymupdf.TEXT_MEDIABOX_CLIP
TEXT_BLOCK = 0


def read_blocks(path: Path) -> list[dict]:
    """Text blocks in PyMuPDF reading order: [{"page": 1-based int, "text": str}]."""
    with pymupdf.open(path) as doc:
        return [
            {"page": page.number + 1, "text": b[4]}
            for page in doc
            for b in page.get_text("blocks", flags=TEXT_FLAGS)
            if b[6] == TEXT_BLOCK and b[4].strip()
        ]
