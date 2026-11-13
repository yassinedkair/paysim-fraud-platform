"""Crée des données fictives pour vérifier dbt et l'entraînement en CI."""

import argparse
import csv
from pathlib import Path

from fraud_platform.config import DataPaths
from fraud_platform.eda import SCHEMA
from fraud_platform.pipeline import build_bronze, build_silver


def prepare(root: Path) -> None:
    paths = DataPaths(root)
    paths.create()
    source = paths.raw / "ci.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(SCHEMA)
        for hour in (1, 25, 49, 521, 522, 632):
            for index in range(120):
                fraud = index % 5 == 0
                writer.writerow([
                    hour, "TRANSFER" if fraud else "PAYMENT", 10 + index,
                    f"C{index}", 1000, 900, "M1", 0, 0, int(fraud), 0,
                ])
    bronze = build_bronze(source, paths)
    build_silver(bronze, paths)
    silver = paths.silver / bronze.name
    print(silver.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    prepare(parser.parse_args().output)
