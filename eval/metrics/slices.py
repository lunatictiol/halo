"""Aggregate per-query metric values overall, by question type and by modality (never the type x modality
cross: cells are too small, see CLAUDE.md)."""

from collections import defaultdict

SLICES = {"by_type": "type", "by_modality": "source"}


def _mean(values: list[float | None]) -> dict:
    present = [v for v in values if v is not None]
    return {"mean": round(sum(present) / len(present), 4) if present else None, "n": len(present)}


def _block(records: list[dict], metrics: list[str]) -> dict:
    return {m: _mean([r[m] for r in records]) for m in metrics}


def summarize(records: list[dict], metrics: list[str]) -> dict:
    out = {"overall": _block(records, metrics)}
    for name, key in SLICES.items():
        groups = defaultdict(list)
        for r in records:
            groups[r[key]].append(r)
        out[name] = {g: _block(rs, metrics) for g, rs in sorted(groups.items())}
    return out
