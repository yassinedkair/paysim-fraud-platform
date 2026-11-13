import pytest

duckdb = pytest.importorskip("duckdb")

from fraud_platform.features import FEATURE_COLUMNS, TARGET_COLUMN, export_features


def test_export_keeps_boundary_hours_in_separate_periods(tmp_path):
    database = tmp_path / "fixture.duckdb"
    with duckdb.connect(str(database)) as db:
        db.execute("create schema gold")
        db.execute("""
            create table gold.fact_transactions as
            select hour as simulation_hour, 10.25 as amount, 'TRANSFER' as transaction_type,
                   true as is_fraud, 'C123' as name_origin
            from (values (520), (521), (631), (632)) as source(hour)
        """)

    output = tmp_path / "transactions.parquet"
    assert export_features(database, output) == [
        ("train", 520, 520, 1, 1), ("validation", 521, 631, 2, 2), ("test", 632, 632, 1, 1),
    ]
    with duckdb.connect() as db:
        exported = db.read_parquet(str(output))
        assert set(exported.columns) == {*FEATURE_COLUMNS, TARGET_COLUMN, "simulation_hour", "split"}
        assert exported.order("simulation_hour").project("hour_of_day").fetchall() == [(15,), (16,), (6,), (7,)]
