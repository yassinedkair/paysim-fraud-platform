"""Expose le modèle LightGBM et son seuil de démonstration."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI
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


def create_app(model_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        directory = model_dir or Path(os.getenv("FRAUD_MODEL_DIR", "artifacts/lightgbm"))
        decision = json.loads((directory / "threshold_margin.json").read_text(encoding="utf-8"))
        threshold = float(decision["validation"]["threshold"])
        if not 0 <= threshold <= 1:
            raise ValueError("Le seuil doit être compris entre 0 et 1")
        app.state.model = joblib.load(directory / "lightgbm.joblib")
        app.state.threshold = threshold
        logger.info("Modèle LightGBM chargé, seuil=%s", threshold)
        yield

    app = FastAPI(title="API de détection de fraude", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/model-info")
    def model_info():
        return {"model": "lightgbm", "features": FEATURE_COLUMNS, "threshold": app.state.threshold}

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
