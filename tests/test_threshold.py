import pytest

pytest.importorskip("sklearn")
pytest.importorskip("duckdb")

from fraud_platform.threshold import (
    choose_operating_threshold, choose_recall_under_error_cap, choose_threshold,
)


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
