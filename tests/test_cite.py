import pytest

from eval.metrics.citation import citation_scores, citation_totals
from halo.generate.cite import ground, parse_sentence, split_sentences

CHUNKS = [{"paper_id": f"p{i}", "section_id": i, "page": i * 10, "text": f"passage {i}"} for i in (1, 2, 3)]


@pytest.mark.parametrize("text,expected", [
    ("A uses BM25 [P1]. B is 0.5 [P2].", ["A uses BM25 [P1].", "B is 0.5 [P2]."]),
    ("A uses BM25. [P1] B is fast. [P2][P3]", ["A uses BM25 [P1].", "B is fast [P2][P3]."]),   # marker after the period
    ("As shown by Smith et al. [P1], it works.", ["As shown by Smith et al. [P1], it works."]),
    ("It uses e.g. Adam [P1]. Fig. 3 shows it [P2].", ["It uses e.g. Adam [P1].", "Fig. 3 shows it [P2]."]),
    ("Accuracy rose from 0.81 to 0.93 [P1].", ["Accuracy rose from 0.81 to 0.93 [P1]."]),
    ("Shown in prior work. [21] Next one [P1].", ["Shown in prior work.", "Next one [P1]."]),
    ("", []),
])
def test_split_sentences(text, expected):
    assert split_sentences(text) == expected


@pytest.mark.parametrize("sentence,expected", [
    ("A uses BM25 [P1].", ("A uses BM25.", [1])),
    ("A [P2] and B [P1, P2][P3].", ("A and B.", [2, 1, 3])),
    ("No citation here.", ("No citation here.", [])),
    ("Shown by Smith [21] and [3, 8] [P1].", ("Shown by Smith and.", [1])),  # bib markers dropped
    ("Lowercase label [p2].", ("Lowercase label.", [2])),
])
def test_parse_sentence(sentence, expected):
    assert parse_sentence(sentence) == expected


def _check(supported: set[tuple[str, int]]):
    """Stub checker: supported iff (claim prefix, section id) is listed and that section is among the passages;
    records calls as (claim, section ids)."""
    calls = []

    def check(claim: str, chunks: list[dict]) -> dict:
        ids = tuple(c["section_id"] for c in chunks)
        calls.append((claim, ids))
        ok = any(claim.startswith(p) and s in ids for p, s in supported)
        return {"verdict": "supported" if ok else "unsupported", "reason": "r", "ms": 1}
    return check, calls


def test_ground_keeps_supported_and_removes_unsupported_and_unattributable_uncited():
    check, calls = _check({("A", 1)})
    g = ground("A uses BM25 [P1][P2]. B is fast [P3]. C has no citation.", CHUNKS, check)
    assert [s["kept"] for s in g["sentences"]] == [True, False, False]
    assert g["final"] == "A uses BM25 [p1 §1 p.10] [p2 §2 p.20]."
    assert g["raw"] == "A uses BM25 [p1 §1 p.10] [p2 §2 p.20]. B is fast [p3 §3 p.30]. C has no citation."
    assert not g["abstained"] and len(calls) == 7   # A once (P1+P2), B: P3 then P1, P2; C: P1, P2, P3
    assert calls[0] == ("A uses BM25.", (1, 2))      # one joint check per sentence, not one per citation


def test_ground_attributes_uncited_sentence_to_supporting_passage():
    check, _ = _check({("A", 1), ("Yes", 2)})
    g = ground("Yes it is. A is true [P1].", CHUNKS, check)
    assert g["sentences"][0]["reattributed"]["n"] == 2 and g["sentences"][0]["cites"] == []
    assert g["final"] == "Yes it is [p2 §2 p.20]. A is true [p1 §1 p.10]."


def test_ground_out_of_range_is_invalid_without_a_call():
    check, calls = _check({("A", 1)})
    g = ground("A is true [P1][P7].", CHUNKS, check)
    assert [c["verdict"] for c in g["sentences"][0]["cites"]] == ["supported", "out_of_range"]
    assert len(calls) == 1


@pytest.mark.parametrize("answer", ["B is wrong [P2].", "Nothing is cited.", ""])
def test_ground_abstains_without_a_grounded_sentence(answer):
    check, _ = _check({("A", 1)})
    assert ground(answer, CHUNKS, check)["abstained"]


def test_ground_parse_error_does_not_keep_sentence():
    g = ground("A is true [P1].", CHUNKS, lambda c, ch: {"verdict": None, "reason": "parse_error", "ms": None})
    assert g["sentences"][0]["kept"] is False and g["abstained"]


def test_citation_scores():
    check, _ = _check({("A", 1)})
    g = ground("A uses BM25 [P1][P2]. B is fast [P3]. C has no citation. D too [P9].", CHUNKS, check)
    s = citation_scores(g)
    assert s["citation_validity"] == pytest.approx(2 / 4)            # A's two (joint verdict) of 4 incl. out of range
    assert s["citation_coverage"] == pytest.approx(3 / 4)            # C is uncited
    assert s["citation_coverage_final"] == pytest.approx(1)          # only A is kept
    assert s["sentences_removed"] == pytest.approx(3 / 4)            # B, C and D
    t = citation_totals([g, None])
    assert t["answers_checked"] == 1 and t["citations"] == 4 and t["out_of_range"] == 1
    assert t["supported"] == 2 and t["unsupported"] == 1 and t["sentences_removed"] == 3


def test_citation_scores_not_applicable():
    assert set(citation_scores(None).values()) == {None}
    abstained = ground("B is fast [P3].", CHUNKS, _check(set())[0])
    s = citation_scores(abstained)
    assert s["citation_validity"] == 0.0 and s["citation_coverage_final"] is None


def test_ground_reattributes_failed_sentence_to_supporting_passage():
    check, calls = _check({("A", 3)})
    g = ground("A is true [P1].", CHUNKS, check)
    s = g["sentences"][0]
    assert s["kept"] and s["grounded"] and s["reattributed"]["n"] == 3
    assert [c["verdict"] for c in s["cites"]] == ["unsupported"]        # validity still sees the original citation
    assert g["final"] == "A is true [p3 §3 p.30]." and not g["abstained"]
    assert calls == [("A is true.", (1,)), ("A is true.", (2,)), ("A is true.", (3,))]
    assert citation_scores(g)["citation_validity"] == 0.0
    assert citation_totals([g])["reattributed"] == 1


def test_ground_out_of_range_only_sentence_is_reattributed_too():
    check, _ = _check({("A", 2)})
    s = ground("A is true [P7].", CHUNKS, check)["sentences"][0]
    assert s["kept"] and s["reattributed"]["n"] == 2
