import random

from eval.runners.calibrate import calibration, confusion, draw


def _pool(n_neg, n_pos):
    return [{"id": f"n{i}", "_negative": True} for i in range(n_neg)] + \
           [{"id": f"p{i}", "_negative": False} for i in range(n_pos)]


def test_draw_oversamples_negatives_up_to_share():
    picked = draw(_pool(20, 100), per_kind=10, negative_share=0.4, rng=random.Random(0))
    assert len(picked) == 10 and sum(x["_negative"] for x in picked) == 4


def test_draw_takes_all_negatives_when_scarce():
    picked = draw(_pool(2, 100), per_kind=10, negative_share=0.4, rng=random.Random(0))
    assert len(picked) == 10 and sum(x["_negative"] for x in picked) == 2


def test_draw_is_seeded():
    pool = _pool(20, 100)
    assert draw(pool, 10, 0.4, random.Random(7)) == draw(pool, 10, 0.4, random.Random(7))


def test_calibration_scores_each_judge_against_human_and_each_other():
    items = [{"item_id": "f1", "kind": "faithfulness"}, {"item_id": "f2", "kind": "faithfulness"},
             {"item_id": "c1", "kind": "correctness"}, {"item_id": "c2", "kind": "correctness"}]
    human = {"f1": "supported", "f2": "unsupported", "c1": "correct", "c2": "incorrect"}
    judged = {"a": {i: {"verdict": human[i]} for i in human},                           # always agrees
              "b": {i: {"verdict": v} for i, v in [("f1", "supported"), ("f2", "supported"),
                                                    ("c1", "correct"), ("c2", "correct")]}}  # always positive
    cal = calibration(items, human, judged)
    assert cal["faithfulness"]["a_vs_human"]["kappa"] == 1.0
    assert cal["faithfulness"]["b_vs_human"] == {"n": 2, "agreement": 0.5, "kappa": 0.0}
    assert cal["correctness"]["a_vs_b"]["agreement"] == 0.5
    assert cal["correctness"]["human_negatives"] == 1


def test_confusion_counts_judge_to_human_pairs():
    items = [{"item_id": "c1", "kind": "correctness"}, {"item_id": "c2", "kind": "correctness"}]
    human = {"c1": "correct", "c2": "incorrect"}
    judged = {"a": {"c1": {"verdict": "correct"}, "c2": {"verdict": "correct"}}}
    assert confusion(items, human, judged)["correctness"]["a"] == {
        "correct->correct": 1, "correct->incorrect": 1, "incorrect->correct": 0, "incorrect->incorrect": 0}
