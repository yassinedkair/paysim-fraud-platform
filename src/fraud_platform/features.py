"""Prépare les variables PaySim et leur séparation chronologique."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

FEATURE_COLUMNS = ("amount", "transaction_type", "hour_of_day")
TARGET_COLUMN = "is_fraud"
TRAIN_LAST_HOUR = 520
VALIDATION_LAST_HOUR = 631

FEATURE_QUERY = f"""
select
    simulation_hour,
    amount,
    transaction_type,
    (simulation_hour - 1) % 24 as hour_of_day,
    is_fraud,
    case
        when simulation_hour <= {TRAIN_LAST_HOUR} then 'train'
        when simulation_hour <= {VALIDATION_LAST_HOUR} then 'validation'
        else 'test'
    end as split
from gold.fact_transactions
"""


def export_features(database: Path, output: Path) -> list[tuple]:
    """Écrit le Parquet et retourne les volumes et fraudes par période."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as staging:
        pending = Path(staging) / output.name
        with duckdb.connect(str(database), read_only=True) as db:
            db.execute(f"copy ({FEATURE_QUERY}) to ? (format parquet, compression zstd)", [str(pending)])
            summary = db.execute("""
                select split, min(simulation_hour), max(simulation_hour),
                       count(*), count_if(is_fraud)
                from read_parquet(?)
                group by split order by min(simulation_hour)
            """, [str(pending)]).fetchall()
        pending.replace(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/gold/fraud.duckdb"))
    parser.add_argument("--output", type=Path, default=Path("data/modeling/transactions.parquet"))
    args = parser.parse_args()
    for split, first, last, rows, frauds in export_features(args.database, args.output):
        print(f"{split}: heures {first}-{last}, {rows} transactions, {frauds} fraudes")


if __name__ == "__main__":
    main()
