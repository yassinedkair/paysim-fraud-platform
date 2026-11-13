"""Choisit un seuil LightGBM à partir des coûts simulés en validation."""

import argparse
import json
from pathlib import Path

import duckdb
import joblib
import numpy as np
from sklearn.metrics import roc_curve

from fraud_platform.features import FEATURE_COLUMNS, TARGET_COLUMN

REFERENCE_COST_RATIO = 20
MAX_ERROR_RATE = 0.15


def choose_recall_under_error_cap(labels, scores) -> dict:
    """Maximise le rappel sous le plafond d'erreur globale."""
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=float)
    fpr, recall, thresholds = roc_curve(labels, scores, drop_intermediate=False)
    positives = int(labels.sum())
    errors = np.rint(fpr * (len(labels) - positives)) + positives - np.rint(recall * positives)
    eligible = np.flatnonzero(errors / len(labels) <= MAX_ERROR_RATE)
    if not eligible.size:
        raise ValueError("Aucun seuil ne respecte le plafond d'erreur globale")
    best_recall = recall[eligible].max()
    tied = eligible[recall[eligible] == best_recall]
    index = tied[np.argmin(errors[tied])]
    threshold = float(thresholds[index])
    if not np.isfinite(threshold):
        threshold = float(np.nextafter(scores.max(), np.inf))
    return summarize_decisions(labels, scores, threshold, REFERENCE_COST_RATIO)


def choose_operating_threshold(labels, scores, min_recall: float = 0.8) -> dict:
    """Minimise les erreurs avec un rappel supérieur à la cible et une erreur <= 15 %."""
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=float)
    fpr, recall, thresholds = roc_curve(labels, scores, drop_intermediate=False)
    positives = int(labels.sum())
    errors = np.rint(fpr * (len(labels) - positives)) + positives - np.rint(recall * positives)
    eligible = np.flatnonzero((recall > min_recall) & (errors / len(labels) <= MAX_ERROR_RATE))
    if not eligible.size:
        raise ValueError("Aucun seuil ne respecte les objectifs sur la validation")
    index = eligible[np.argmin(errors[eligible])]
    return summarize_decisions(labels, scores, float(thresholds[index]), REFERENCE_COST_RATIO)


def choose_threshold(labels, scores, missed_fraud_cost: int) -> dict:
    """Minimise FP + coût d'une fraude manquée × FN, sans séparer les scores égaux."""
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=float)
    positives = int(labels.sum())
    negatives = len(labels) - positives
    fpr, tpr, thresholds = roc_curve(labels, scores, drop_intermediate=False)
    false_positives = np.rint(fpr * negatives).astype(int)
    true_positives = np.rint(tpr * positives).astype(int)
    costs = false_positives + missed_fraud_cost * (positives - true_positives)
    index = int(np.argmin(costs))  # En cas d'égalité, privilégie le seuil le plus haut.
    threshold = float(thresholds[index])
    if not np.isfinite(threshold):
        threshold = float(np.nextafter(scores.max(), np.inf))
    return summarize_decisions(labels, scores, threshold, missed_fraud_cost)


def summarize_decisions(labels, scores, threshold: float, missed_fraud_cost: int) -> dict:
    labels = np.asarray(labels, dtype=bool)
    alerts = np.asarray(scores) >= threshold
    tp = int(np.count_nonzero(alerts & labels))
    fp = int(np.count_nonzero(alerts & ~labels))
    fn = int(np.count_nonzero(~alerts & labels))
    return {
        "threshold": threshold, "missed_fraud_cost": missed_fraud_cost,
        "alerts": tp + fp, "true_positives": tp, "false_positives": fp,
        "false_negatives": fn, "cost": fp + missed_fraud_cost * fn,
        "error_rate": (fp + fn) / len(labels),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/modeling/transactions.parquet"))
    parser.add_argument("--model", type=Path, default=Path("artifacts/lightgbm/lightgbm.joblib"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/lightgbm/threshold.json"))
    args = parser.parse_args()
    with duckdb.connect() as db:
        validation = db.read_parquet(str(args.source)).filter("split = 'validation'").df()
    labels = validation[TARGET_COLUMN]
    scores = joblib.load(args.model).predict_proba(validation[list(FEATURE_COLUMNS)])[:, 1]
    scenarios = [choose_threshold(labels, scores, ratio) for ratio in (5, REFERENCE_COST_RATIO, 100)]
    report = {
        "split": "validation",
        "false_alert_cost": 1,
        "reference": scenarios[1],
        "operating_threshold": choose_operating_threshold(labels, scores),
        "recall_under_error_cap": choose_recall_under_error_cap(labels, scores),
        "default_at_reference_cost": summarize_decisions(labels, scores, 0.5, REFERENCE_COST_RATIO),
        "scenarios": scenarios,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
