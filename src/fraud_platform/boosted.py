"""Entraîne LightGBM et mesure sa performance sur la validation PaySim."""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from fraud_platform.baseline import evaluate_scores, load_train_validation
from fraud_platform.features import FEATURE_COLUMNS, TARGET_COLUMN


def train_lightgbm(source: Path, output: Path) -> dict:
    train, validation = load_train_validation(source)
    labels = train[TARGET_COLUMN]
    positives = int(labels.sum())
    negative_to_positive = (len(labels) - positives) / positives

    categories = ["transaction_type", "hour_of_day"]
    preprocess = ColumnTransformer([
        ("categories", OrdinalEncoder(
            handle_unknown="use_encoded_value", unknown_value=-1, dtype=np.int32,
        ), categories),
    ], remainder="passthrough", verbose_feature_names_out=False).set_output(transform="pandas")
    classifier = LGBMClassifier(
        objective="binary", n_estimators=150, learning_rate=0.05, num_leaves=31,
        scale_pos_weight=negative_to_positive, boost_from_average=False,
        random_state=42, n_jobs=4, verbosity=-1,
    )
    model = Pipeline([("preprocess", preprocess), ("classifier", classifier)])
    features = list(FEATURE_COLUMNS)
    model.fit(train[features], labels, classifier__categorical_feature=categories)
    scores = model.predict_proba(validation[features])[:, 1]
    report = {
        "model": "lightgbm", "features": features,
        "scale_pos_weight": negative_to_positive,
        "boost_from_average": False,
        "train_rows": len(train), "train_frauds": positives,
        **evaluate_scores(validation[TARGET_COLUMN], scores),
    }
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output / "lightgbm.joblib")
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/modeling/transactions.parquet"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/lightgbm"))
    args = parser.parse_args()
    print(json.dumps(train_lightgbm(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
