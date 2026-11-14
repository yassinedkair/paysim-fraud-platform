"""Construit fact_reclamations et entraîne un classifieur de produits CFPB."""

import argparse
import csv
import json
from datetime import date
from pathlib import Path

import joblib
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import make_pipeline

FIELDS = ("Complaint ID", "Date received", "Product", "Consumer complaint narrative")


def load_complaints(source: Path) -> list[dict]:
    records = []
    seen_ids = set()
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = [field for field in FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Colonnes CFPB manquantes : " + ", ".join(missing))
        for row in reader:
            complaint_id, received, product, narrative = ((row[field] or "").strip() for field in FIELDS)
            if not all((complaint_id, received, product, narrative)) or complaint_id in seen_ids:
                continue
            records.append({
                "complaint_id": complaint_id, "date_received": date.fromisoformat(received),
                "product": product, "narrative": narrative,
            })
            seen_ids.add(complaint_id)
    return sorted(records, key=lambda row: (row["date_received"], row["complaint_id"]))


def build_and_train(source: Path, output: Path) -> dict:
    records = load_complaints(source)
    days = sorted({row["date_received"] for row in records})
    if len(days) < 2:
        raise ValueError("Deux dates distinctes au minimum sont nécessaires")
    cutoff = days[int(len(days) * 0.8)]
    train, test = [], []
    for row in records:
        (train if row["date_received"] < cutoff else test).append(row)
    if len({row["product"] for row in train}) < 2:
        raise ValueError("Deux produits au minimum sont nécessaires en entraînement")

    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), max_features=30_000),
        LogisticRegression(class_weight="balanced", max_iter=300),
    )
    model.fit([row["narrative"] for row in train], [row["product"] for row in train])
    actual = [row["product"] for row in test]
    predicted = model.predict([row["narrative"] for row in test])
    report = {
        "test_start": cutoff.isoformat(), "train_rows": len(train), "test_rows": len(test),
        "accuracy": float(accuracy_score(actual, predicted)),
        "metrics": classification_report(actual, predicted, output_dict=True, zero_division=0),
    }
    output.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(records), output / "fact_reclamations.parquet", compression="zstd")
    joblib.dump(model, output / "product_classifier.joblib")
    (output / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/complaints"))
    args = parser.parse_args()
    print(json.dumps(build_and_train(args.csv, args.output), indent=2))
