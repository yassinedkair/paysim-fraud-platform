"""Calcule les contributions SHAP intégrées à LightGBM."""

import json
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from scipy.special import expit

from fraud_platform.features import FEATURE_COLUMNS


def explain_lightgbm(source: Path, directory: Path) -> dict:
    model = joblib.load(directory / "lightgbm.joblib")
    threshold = json.loads((directory / "threshold_margin.json").read_text(encoding="utf-8"))
    cutoff = threshold["validation"]["threshold"]
    features = list(FEATURE_COLUMNS)
    with duckdb.connect() as db:
        validation = db.read_parquet(str(source)).filter("split = 'validation'").project(", ".join(features)).df()
    sample = validation.sample(n=min(2000, len(validation)), random_state=42)
    example = {"amount": 500.0, "transaction_type": "TRANSFER", "hour_of_day": 0}
    inputs = pd.concat([sample, pd.DataFrame([example])], ignore_index=True)
    transformed = model.named_steps["preprocess"].transform(inputs)
    booster = model.named_steps["classifier"].booster_
    values = booster.predict(transformed, pred_contrib=True, validate_features=True)
    scores = model.predict_proba(inputs)[:, 1]
    np.testing.assert_allclose(expit(values.sum(axis=1)), scores, rtol=1e-8, atol=1e-10)

    names = list(transformed.columns)
    importance = dict(zip(names, np.abs(values[:-1, :-1]).mean(axis=0).tolist(), strict=True))
    importance = dict(sorted(importance.items(), key=lambda item: item[1], reverse=True))
    report = {
        "method": "LightGBM TreeSHAP", "split": "validation", "sample_rows": len(sample),
        "scale": "log_odds", "mean_absolute_contribution": importance,
        "example": {
            "features": example, "score": float(scores[-1]), "threshold": cutoff,
            "alert": bool(scores[-1] >= cutoff), "base_value": float(values[-1, -1]),
            "contributions": dict(zip(names, values[-1, :-1].tolist(), strict=True)),
        },
    }
    (directory / "shap.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    fig = Figure(figsize=(7, 3.2), layout="constrained")
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.barh(list(importance), list(importance.values()), color="#286B89")
    ax.invert_yaxis()
    ax.set_xlabel("Contribution SHAP absolue moyenne (log-odds)")
    ax.set_title(f"Variables LightGBM sur {len(sample):,} transactions de validation")
    fig.savefig(directory / "shap_importance.png", dpi=160)
    return report


if __name__ == "__main__":
    print(json.dumps(explain_lightgbm(Path("data/modeling/transactions.parquet"), Path("artifacts/lightgbm")), indent=2))
