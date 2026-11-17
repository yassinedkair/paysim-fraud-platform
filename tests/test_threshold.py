import pytest

pytest.importorskip("sklearn")
pytest.importorskip("duckdb")

from fraud_platform.threshold import (
    choose_operating_threshold, choose_recall_under_error_cap, choose_threshold, choose_balanced_threshold,
)


def test_balanced_threshold_does_not_trade_all_precision_for_recall():
    result = choose_balanced_threshold(
        [True] * 5 + [False] * 95,
        [0.99, 0.98, 0.97, 0.96, 0.1] + [0.95] * 20 + [0.01] * 75,
    )
    assert result['precision'] == 1
    assert result['recall'] == 0.8
    assert result['targets_met'] is False


def test_balanced_threshold_accepts_joint_targets():
    result = choose_balanced_threshold([True] * 10 + [False] * 90, [0.9] * 9 + [0.1] + [0.85] + [0.01] * 89)
    assert result['targets_met'] is True
    assert result['precision'] > 0.8
    assert result['recall'] > 0.8
    assert result['accuracy'] > 0.8


def test_balanced_threshold_rejects_single_class():
    with pytest.raises(ValueError, match='deux classes'):
        choose_balanced_threshold([False, False], [0.1, 0.2])


def test_balanced_threshold_supports_sixty_percent_target():
    labels = [True] * 10 + [False] * 90
    scores = [0.9] * 7 + [0.1] * 3 + [0.9] * 3 + [0.01] * 87
    result = choose_balanced_threshold(labels, scores, target=.6)
    assert result['targets_met'] is True
    assert result['precision'] == pytest.approx(10 / 13)
    assert result['recall'] == 1
    assert choose_balanced_threshold(labels, scores)['targets_met'] is False


def test_threshold_keeps_equal_scores_together_and_minimizes_cost():
    result = choose_threshold([True, False, True, False], [0.9, 0.8, 0.8, 0.1], 5)
    assert result["threshold"] == 0.8
    assert result["true_positives"] == 2
    assert result["false_positives"] == 1
    assert result["cost"] == 1


def test_operating_threshold_requires_strictly_more_than_eighty_percent_recall():
    result = choose_operating_threshold(
        [True] * 5 + [False] * 15,
        [0.95, 0.94, 0.93, 0.92, 0.8] + [0.85] + [0.1] * 14,
    )
    assert result["threshold"] == 0.8
    assert result["recall"] == 1.0
    assert result["error_rate"] == 0.05


def test_error_cap_rules_out_a_threshold_with_higher_recall():
    result = choose_recall_under_error_cap(
        [True, False, False, False, True] + [False] * 5,
        [0.9, 0.8, 0.7, 0.6, 0.5] + [0.1] * 5,
    )
    assert result["threshold"] == 0.9
    assert result["recall"] == 0.5
    assert result["error_rate"] == 0.1
