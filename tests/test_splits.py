from scripts.make_splits import build_splits, check_invariants

# Toy corpus: 6 source papers (2 questions each), 4 distractors; cs.AI vs math.ST categories.
QRELS = {f"q{d}{i}": {"doc_id": f"s{d}", "section_id": i} for d in range(6) for i in range(2)}
PDF_URLS = {**{f"s{d}": "" for d in range(6)}, **{f"x{d}": "" for d in range(4)}}
CATS = {**{f"s{d}": ["cs.AI"] for d in range(6)},
        "x0": ["cs.AI"], "x1": ["cs.AI"], "x2": ["math.ST"], "x3": ["math.ST"]}
ARGS = dict(held_out_papers=2, dev_sample_min_questions=4, dev_distractors=2)


def test_same_seed_gives_identical_splits():
    assert build_splits(QRELS, PDF_URLS, CATS, 7, **ARGS) == build_splits(QRELS, PDF_URLS, CATS, 7, **ARGS)


def test_splits_are_disjoint_and_sized():
    s = build_splits(QRELS, PDF_URLS, CATS, 7, **ARGS)
    check_invariants(s)
    assert len(s["held_out"]["paper_ids"]) == 2
    assert len(s["abstention_set"]["query_ids"]) == 4
    assert len(s["dev_sample"]["query_ids"]) >= 4
    assert len(s["full"]["query_ids"]) == 12 - 4
    # Only cs.AI distractors match the cs.AI dev sources.
    assert s["dev_slice"]["distractor_paper_ids"] == ["x0", "x1"]
    assert s["dev_slice"]["distractors_category_matched"] == 2


def test_falls_back_to_random_distractors_when_too_few_match():
    s = build_splits(QRELS, PDF_URLS, CATS, 7, **{**ARGS, "dev_distractors": 3})
    assert len(s["dev_slice"]["distractor_paper_ids"]) == 3
    assert s["dev_slice"]["distractors_category_matched"] == 2
