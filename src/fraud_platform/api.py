"""Expose le modèle LightGBM et son seuil de démonstration."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from fraud_platform.features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    amount: float = Field(ge=0, allow_inf_nan=False)
    transaction_type: Literal["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]
    hour_of_day: int = Field(ge=0, le=23)


class Prediction(BaseModel):
    score: float
    threshold: float
    alert: bool


def load_ieee_model(directory: Path):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((directory / "validation.json").read_text(encoding="utf-8"))
    model = joblib.load(directory / "model.joblib")
    return model, manifest, validation[manifest["selected_model"]]


def create_app(model_dir: Path | None = None, ieee_model_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        directory = model_dir or Path(os.getenv("FRAUD_MODEL_DIR", "artifacts/lightgbm"))
        decision = json.loads((directory / "threshold_margin.json").read_text(encoding="utf-8"))
        threshold = float(decision["validation"]["threshold"])
        if not 0 <= threshold <= 1:
            raise ValueError("Le seuil doit être compris entre 0 et 1")
        app.state.model = joblib.load(directory / "lightgbm.joblib")
        app.state.threshold = threshold
        app.state.validation = {
            key: decision["validation"][key]
            for key in ("precision", "recall", "accuracy", "targets_met")
            if key in decision["validation"]
        }
        logger.info("Modèle LightGBM chargé, seuil=%s", threshold)
        ieee_directory = ieee_model_dir or Path(os.getenv("IEEE_MODEL_DIR", "artifacts/ieee_cis_60"))
        app.state.ieee = load_ieee_model(ieee_directory) if ieee_directory.is_dir() else None
        yield

    app = FastAPI(title="API de détection de fraude", lifespan=lifespan)
    web = Path(__file__).with_name("web")
    app.mount("/ui-assets", StaticFiles(directory=web), name="ui-assets")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(web / "index.html", media_type="text/html")

    @app.get("/ieee", include_in_schema=False)
    def ieee_dashboard():
        return FileResponse(web / "ieee.html", media_type="text/html")

    def ieee_artifacts():
        if app.state.ieee is None:
            raise HTTPException(503, "Modèle IEEE-CIS indisponible. Entraîne-le et configure IEEE_MODEL_DIR.")
        return app.state.ieee

    @app.get("/ieee/model-info")
    def ieee_info():
        _, manifest, report = ieee_artifacts()
        return {"model": manifest["selected_model"], "threshold": manifest["threshold"],
                "validation": {key: report[key] for key in ("precision", "recall", "accuracy")}}

    @app.get("/ieee/example")
    def ieee_example():
        ieee_artifacts()
        directory = Path(os.getenv("IEEE_DATA_DIR", "data/raw"))
        source = directory / "train_transaction.csv"
        if not source.is_file():
            raise HTTPException(404, "CSV IEEE-CIS absent. Tu peux importer une transaction JSON.")
        transactions = pd.read_csv(source, nrows=1, dtype=str).drop(columns="isFraud")
        return json.loads(transactions.to_json(orient="records"))[0]

    @app.post("/ieee/predict", response_model=Prediction)
    def ieee_predict(transaction: dict[str, str | int | float | None]):
        import math

        from fraud_platform.ieee_experiment import CATEGORICAL, feature_frame

        model, manifest, _ = ieee_artifacts()
        derived = {"hour", "day_in_week"}
        if manifest.get("enhanced_features"):
            derived.update({"amount_fraction", "missing_fields", "card_address"})
        columns = [key for key in manifest["raw_feature_columns"]
                   if key not in derived and not key.endswith("_origin_day")]
        values = {}
        try:
            timestamp = float(transaction["TransactionDT"])
            if not math.isfinite(timestamp) or timestamp < 0 or not timestamp.is_integer():
                raise ValueError("TransactionDT doit être un nombre entier de secondes positif ou nul.")
            for key in columns:
                value = transaction.get(key)
                if value in (None, ""):
                    values[key] = None if key in CATEGORICAL else float("nan")
                elif key in CATEGORICAL:
                    values[key] = str(value)
                else:
                    values[key] = float(value)
                    if not math.isfinite(values[key]):
                        raise ValueError(f"{key} doit être un nombre fini.")
            if not math.isfinite(values["TransactionAmt"]) or values["TransactionAmt"] < 0:
                raise ValueError("TransactionAmt doit être renseigné et positif ou nul.")
        except (KeyError, ValueError, OverflowError) as error:
            raise HTTPException(422, f"Transaction IEEE-CIS invalide. {error}") from error
        values["TransactionDT"] = int(timestamp)
        frame = pd.DataFrame([values]).astype({key: "float32" for key in columns if key not in CATEGORICAL})
        features = feature_frame(frame, manifest.get("enhanced_features", False))
        score = float(model.predict_proba(features)[0, 1])
        threshold = float(manifest["threshold"])
        return Prediction(score=score, threshold=threshold, alert=score >= threshold)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/model-info")
    def model_info():
        return {"model": "lightgbm", "features": FEATURE_COLUMNS, "threshold": app.state.threshold,
                "validation": app.state.validation}

    @app.post("/predict", response_model=Prediction)
    def predict(transaction: Transaction):
        inputs = pd.DataFrame([transaction.model_dump()], columns=FEATURE_COLUMNS)
        score = float(app.state.model.predict_proba(inputs)[0, 1])
        threshold = app.state.threshold
        alert = score >= threshold
        logger.info("Prédiction terminée, alert=%s", alert)
        return Prediction(score=score, threshold=threshold, alert=alert)

    return app


app = create_app()
