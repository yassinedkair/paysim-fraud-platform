"""Enregistre les modèles et leurs rapports existants dans MLflow local."""

import json
from pathlib import Path

import joblib
import mlflow
from mlflow.tracking import MlflowClient

EXPERIMENT_NAME = "fraud-detection-paysim"
VALIDATION_METRICS = ("average_precision", "pr_auc", "precision", "recall", "f1")


def record_experiments(artifacts: Path) -> dict[str, str]:
    tracking = (artifacts / "mlflow").resolve()
    tracking.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{(tracking / 'tracking.db').as_posix()}")
    client = MlflowClient()
    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    experiment_id = experiment.experiment_id if experiment else client.create_experiment(
        EXPERIMENT_NAME, artifact_location=(tracking / "runs").as_uri(),
    )
    runs = {}
    for folder, filename in (("baseline", "logistic_regression.joblib"), ("lightgbm", "lightgbm.joblib")):
        directory = artifacts / folder
        model_path = directory / filename
        report_path = directory / "validation.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        classifier = joblib.load(model_path).named_steps["classifier"]
        with mlflow.start_run(experiment_id=experiment_id, run_name=report["model"]) as run:
            mlflow.log_params({
                **classifier.get_params(),
                "features": ",".join(report["features"]),
                "train_rows": report["train_rows"],
                "train_frauds": report["train_frauds"],
                "validation_threshold": report["threshold"],
            })
            mlflow.log_metrics({f"validation_{name}": report[name] for name in VALIDATION_METRICS})
            mlflow.log_artifact(str(model_path), artifact_path="model")
            mlflow.log_artifact(str(report_path), artifact_path="reports")
            if folder == "lightgbm":
                decision_path = directory / "threshold_margin.json"
                decision = json.loads(decision_path.read_text(encoding="utf-8"))
                mlflow.log_param("demo_threshold", decision["validation"]["threshold"])
                mlflow.log_metrics({
                    f"demo_validation_{name}": decision["validation"][name]
                    for name in ("recall", "precision", "error_rate")
                })
                mlflow.log_metrics({
                    f"demo_reused_test_{name}": decision["reused_test_diagnostic"][name]
                    for name in ("recall", "precision", "error_rate")
                })
                mlflow.log_artifact(str(decision_path), artifact_path="reports")
                for explanation in ("shap.json", "shap_importance.png"):
                    path = directory / explanation
                    if path.is_file():
                        mlflow.log_artifact(str(path), artifact_path="explanations")
                mlflow.set_tag("test_status", "reused_diagnostic")
            runs[report["model"]] = run.info.run_id
    return runs


if __name__ == "__main__":
    print(json.dumps(record_experiments(Path("artifacts")), indent=2))
