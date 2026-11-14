"""Compare les distributions PaySim entre validation et test."""

import argparse
import json
from pathlib import Path

import duckdb
import joblib
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset

from fraud_platform.features import FEATURE_COLUMNS, TARGET_COLUMN
from fraud_platform.threshold import REFERENCE_COST_RATIO, summarize_decisions


def build_monitoring_report(source: Path, model_dir: Path, output: Path) -> dict:
    model = joblib.load(model_dir / "lightgbm.joblib")
    threshold = json.loads((model_dir / "threshold_margin.json").read_text(
        encoding="utf-8"
    ))["validation"]["threshold"]
    features = list(FEATURE_COLUMNS)
    definition = DataDefinition(
        numerical_columns=["amount", "fraud_score"],
        categorical_columns=["transaction_type", "hour_of_day"],
    )
    datasets = {}
    periods = {}
    with duckdb.connect() as db:
        transactions = db.read_parquet(str(source))
        for period in ("validation", "test"):
            frame = transactions.filter(f"split = '{period}'").project(
                ", ".join([*features, TARGET_COLUMN, "simulation_hour"])
            ).df()
            if frame.empty:
                raise ValueError(f"Période vide : {period}")
            scores = model.predict_proba(frame[features])[:, 1]
            distribution = frame[features].assign(fraud_score=scores)
            sample = distribution.sample(n=min(5_000, len(frame)), random_state=42)
            datasets[period] = Dataset.from_pandas(sample, data_definition=definition)
            periods[period] = {
                "rows": len(frame),
                "sample_rows": len(sample),
                "first_hour": int(frame["simulation_hour"].min()),
                "last_hour": int(frame["simulation_hour"].max()),
                "fraud_rate": float(frame[TARGET_COLUMN].mean()),
                **summarize_decisions(frame[TARGET_COLUMN], scores, threshold, REFERENCE_COST_RATIO),
            }

    snapshot = Report([DataDriftPreset()]).run(datasets["test"], datasets["validation"])
    output.mkdir(parents=True, exist_ok=True)
    snapshot.save_html(str(output / "drift.html"))
    (output / "drift.json").write_text(snapshot.json(), encoding="utf-8")
    summary = {"reference": "validation", "current": "test", "periods": periods}
    (output / "performance.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/modeling/transactions.parquet"))
    parser.add_argument("--model-dir", type=Path, default=Path("artifacts/lightgbm"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/monitoring"))
    args = parser.parse_args()
    print(json.dumps(build_monitoring_report(args.source, args.model_dir, args.output), indent=2))
