import pytest

from eval.metrics.agreement import agreement


def test_perfect_agreement_has_kappa_one():
    a = ["correct", "incorrect", "correct", "incorrect"]
    assert agreement(a, a) == {"n": 4, "agreement": 1.0, "kappa": 1.0}


def test_hand_computed_kappa():
    # 2x2 table: both yes 2, both no 1, a-yes/b-no 1. po = 3/4; pe = (3/4)(2/4) + (1/4)(2/4) = 1/2; k = 0.5.
    a = ["y", "y", "y", "n"]
    b = ["y", "y", "n", "n"]
    assert agreement(a, b) == {"n": 4, "agreement": 0.75, "kappa": 0.5}


def test_always_positive_judge_has_high_agreement_but_zero_kappa():
    human = ["s"] * 9 + ["u"]
    judge = ["s"] * 10
    r = agreement(human, judge)
    assert r["agreement"] == 0.9 and r["kappa"] == pytest.approx(0.0)


def test_unlabeled_items_are_dropped():
    assert agreement(["y", None, "n"], ["y", "n", None])["n"] == 1


def test_single_shared_label_has_undefined_kappa():
    assert agreement(["y", "y"], ["y", "y"]) == {"n": 2, "agreement": 1.0, "kappa": None}


def test_nothing_labeled():
    assert agreement([None], ["y"]) == {"n": 0, "agreement": None, "kappa": None}
