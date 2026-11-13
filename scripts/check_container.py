"""Vérifie les routes HTTP du conteneur de CI."""

import sys
import time

import httpx


def check(url: str) -> None:
    with httpx.Client(base_url=url, timeout=5, trust_env=False) as client:
        for _ in range(30):
            try:
                response = client.get("/health")
                if response.status_code == 200 and response.json() == {"status": "ok"}:
                    break
            except httpx.TransportError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Le conteneur ne répond pas sur /health")

        info = client.get("/model-info").raise_for_status().json()
        assert info["model"] == "lightgbm"
        transaction = {"amount": 500, "transaction_type": "TRANSFER", "hour_of_day": 0}
        prediction = client.post("/predict", json=transaction).raise_for_status().json()
        assert 0 <= prediction["score"] <= 1
        assert prediction["threshold"] == info["threshold"]
        assert prediction["alert"] == (prediction["score"] >= info["threshold"])
        assert client.post("/predict", json=transaction | {"amount": -1}).status_code == 422
        print("Routes Docker vérifiées.")


if __name__ == "__main__":
    check(sys.argv[1])
