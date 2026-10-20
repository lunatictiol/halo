"""Per-query citation metrics from a grounding record (halo.generate.cite.ground). None = not applicable
(no answer was generated, or nothing to measure) and is excluded from means (D17).

- citation_validity: share of the raw answer's citations whose passage supports the sentence. Out-of-range
  numbers count as invalid; checker parse failures are excluded. These are the pipeline checker's own
  verdicts ("self-checked", D33), not an independent judge.
- citation_coverage: share of raw-answer sentences with at least one citation.
- citation_coverage_final: share of sentences kept after the check that carry a supported citation
  (None if the check abstained).
- sentences_removed: share of raw-answer sentences the check removed.
"""


def _share(num: int, den: int) -> float | None:
    return num / den if den else None


def citation_scores(grounding: dict | None) -> dict:
    if not grounding or not grounding["sentences"]:
        return {"citation_validity": None, "citation_coverage": None, "citation_coverage_final": None,
                "sentences_removed": None}
    sents = grounding["sentences"]
    verdicts = [c["verdict"] for s in sents for c in s["cites"] if c["verdict"] is not None]
    kept = [s for s in sents if s["kept"]]
    return {"citation_validity": _share(sum(v == "supported" for v in verdicts), len(verdicts)),
            "citation_coverage": _share(sum(bool(s["cites"]) for s in sents), len(sents)),
            "citation_coverage_final": None if grounding["abstained"] else
            _share(sum(s["grounded"] is True for s in kept), len(kept)),
            "sentences_removed": _share(sum(not s["kept"] for s in sents), len(sents))}


def citation_totals(groundings: list[dict | None]) -> dict:
    """Micro-averaged counts over all answers, next to the per-query means."""
    sents = [s for g in groundings if g for s in g["sentences"]]
    cites = [c for s in sents for c in s["cites"]]
    return {"answers_checked": sum(bool(g) for g in groundings), "sentences": len(sents),
            "sentences_cited": sum(bool(s["cites"]) for s in sents),
            "sentences_removed": sum(not s["kept"] for s in sents), "citations": len(cites),
            "supported": sum(c["verdict"] == "supported" for c in cites),
            "unsupported": sum(c["verdict"] == "unsupported" for c in cites),
            "out_of_range": sum(c["verdict"] == "out_of_range" for c in cites),
            "check_errors": sum(c["verdict"] is None for c in cites),
            "reattributed": sum(bool(s.get("reattributed")) for s in sents),
            "grounding_abstentions": sum(bool(g and g["abstained"]) for g in groundings)}
