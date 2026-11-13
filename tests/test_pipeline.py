import csv
from decimal import Decimal

import pyarrow.parquet as pq

from fraud_platform.config import DataPaths
from fraud_platform.eda import SCHEMA
from fraud_platform.pipeline import build_bronze, build_layers, build_silver


def test_silver_uses_bronze_without_original_csv(tmp_path):
    source = tmp_path / "sample.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(SCHEMA)
        writer.writerow([1, "PAYMENT", "1.50", "C1", 2, 0.5, "M1", 0, 0, 0, 0])
    paths = DataPaths(tmp_path / "data")
    bronze = build_bronze(source, paths)
    source.unlink()

    assert build_silver(bronze, paths) == {"silver": 1, "quarantine": 0}
    assert build_silver(bronze, paths) == {"silver": 1, "quarantine": 0}
    silver, = paths.silver.glob("*.parquet")
    assert pq.read_table(silver).to_pylist()[0]["amount"] == Decimal("1.50")


def test_build_layers_routes_rejects_and_replaces_on_retry(tmp_path):
    source = tmp_path / "sample.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(SCHEMA)
        writer.writerow([1, "PAYMENT", "1.123456789012", "C1", 2, 1, "M1", 0, 0, 0, 0])
        writer.writerow([1, "PAYMENT", "-1", "C2", 2, 1, "M2", 0, 0, 0, 0])

    paths = DataPaths(tmp_path / "data")
    expected = {"bronze": 2, "silver": 1, "quarantine": 1}
    assert build_layers(source, paths) == expected
    assert build_layers(source, paths) == expected

    tables = {}
    for name, count in expected.items():
        path, = getattr(paths, name).glob("*.parquet")
        tables[name] = pq.read_table(path).to_pylist()
        assert len(tables[name]) == count

    assert tables["bronze"][0]["amount"] == "1.123456789012"
    assert tables["silver"][0]["amount"] == Decimal("1.123456789012")
    assert tables["silver"][0]["transaction_id"] == tables["bronze"][0]["transaction_id"]
    assert tables["quarantine"][0]["transaction_id"] == tables["bronze"][1]["transaction_id"]
    assert tables["quarantine"][0]["rejection_reason"].startswith("amount:")
