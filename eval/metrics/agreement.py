"""Judge-vs-human agreement: raw agreement and Cohen's kappa over paired binary labels (M7, D39).

Kappa corrects raw agreement for chance: with ~95% positives, a judge that always says "supported" agrees 95%
of the time and has kappa 0. Items either rater left unlabeled (None) are dropped before scoring.
"""

from sklearn.metrics import cohen_kappa_score


def agreement(a: list[str | None], b: list[str | None]) -> dict:
    pairs = [(x, y) for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    if not pairs:
        return {"n": 0, "agreement": None, "kappa": None}
    xs, ys = zip(*pairs)
    agree = sum(x == y for x, y in pairs) / len(pairs)
    # Kappa is undefined when both raters used a single, identical label (chance agreement is 1).
    kappa = None if len(set(xs) | set(ys)) == 1 else float(cohen_kappa_score(xs, ys))
    return {"n": len(pairs), "agreement": round(agree, 4), "kappa": None if kappa is None else round(kappa, 4)}
