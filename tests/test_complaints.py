import csv

import pytest

pytest.importorskip("sklearn")
pytest.importorskip("duckdb")

import pyarrow.parquet as pq

from fraud_platform.complaints import FIELDS, build_and_train


def test_complaints_exports_fact_and_evaluates_later_dates(tmp_path):
    source = tmp_path / "complaints.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        for day in range(1, 6):
            writer.writerow([f"a{day}", f"2024-01-0{day}", "Credit card", "card billing fee"])
            writer.writerow([f"b{day}", f"2024-01-0{day}", "Mortgage", "home loan escrow"])
        writer.writerow(["a1", "2024-01-01", "Credit card", "card billing fee"])
        writer.writerow(["empty", "2024-01-01", "Mortgage", ""])

    output = tmp_path / "output"
    report = build_and_train(source, output)
    assert report["test_start"] == "2024-01-05"
    assert (report["train_rows"], report["test_rows"]) == (8, 2)
    assert report["accuracy"] == 1
    assert pq.read_metadata(output / "fact_reclamations.parquet").num_rows == 10
