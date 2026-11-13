from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("duckdb")
pytest.importorskip("pandas")

import numpy as np
from fastapi.testclient import TestClient

from fraud_platform import api


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "threshold_margin.json").write_text('{"validation":{"threshold":0.6}}')
    model = Mock()
    model.predict_proba.return_value = np.array([[0.4, 0.6]])
    monkeypatch.setattr(api.joblib, "load", lambda _: model)
    with TestClient(api.create_app(tmp_path)) as client:
        yield client


def test_predict_uses_saved_threshold_and_alerts_at_equality(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/model-info").json()["threshold"] == 0.6
    response = client.post("/predict", json={"amount": 500, "transaction_type": "TRANSFER", "hour_of_day": 0})
    assert response.status_code == 200
    assert response.json() == {"score": 0.6, "threshold": 0.6, "alert": True}


@pytest.mark.parametrize("field,value", [("amount", -1), ("transaction_type", "OTHER"), ("hour_of_day", 24)])
def test_predict_rejects_invalid_transaction(client, field, value):
    payload = {"amount": 500, "transaction_type": "TRANSFER", "hour_of_day": 0}
    payload[field] = value
    assert client.post("/predict", json=payload).status_code == 422
