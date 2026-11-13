"""Entraîne une régression logistique sur PaySim et mesure la validation."""

import argparse
import json
from pathlib import Path

import duckdb
import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc, average_precision_score, confusion_matrix, f1_score,
    precision_recall_curve, precision_score, recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from fraud_platform.features import FEATURE_COLUMNS, TARGET_COLUMN


def load_train_validation(source: Path):
    columns = [*FEATURE_COLUMNS, TARGET_COLUMN]
    with duckdb.connect() as db:
        train = db.read_parquet(str(source)).filter("split = 'train'").project(", ".join(columns)).df()
        validation = db.read_parquet(str(source)).filter("split = 'validation'").project(", ".join(columns)).df()
    return train, validation


def evaluate_scores(labels, scores, threshold: float = 0.5) -> dict:
    predictions = scores >= threshold
    precision_curve, recall_curve, _ = precision_recall_curve(labels, scores)
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[False, True]).ravel()
    return {
        "validation_rows": len(labels),
        "validation_frauds": int(labels.sum()),
        "average_precision": float(average_precision_score(labels, scores)),
        "pr_auc": float(auc(recall_curve, precision_curve)),
        "threshold": threshold,
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def train_baseline(source: Path, output: Path) -> dict:
    train, validation = load_train_validation(source)

    preprocess = ColumnTransformer([
        ("amount", Pipeline([
            ("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
            ("scale", StandardScaler()),
        ]), ["amount"]),
        ("categories", OneHotEncoder(handle_unknown="ignore"), ["transaction_type", "hour_of_day"]),
    ])
    model = Pipeline([
        ("preprocess", preprocess),
        ("classifier", LogisticRegression(class_weight="balanced", max_iter=200)),
    ])
    features = list(FEATURE_COLUMNS)
    model.fit(train[features], train[TARGET_COLUMN])
    labels = validation[TARGET_COLUMN]
    scores = model.predict_proba(validation[features])[:, 1]
    report = {
        "model": "logistic_regression",
        "features": features,
        "class_weight": "balanced",
        "train_rows": len(train),
        "train_frauds": int(train[TARGET_COLUMN].sum()),
        **evaluate_scores(labels, scores),
    }
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output / "logistic_regression.joblib")
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/modeling/transactions.parquet"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/baseline"))
    args = parser.parse_args()
    print(json.dumps(train_baseline(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
