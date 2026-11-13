"""Construit les couches locales Bronze, Silver et Quarantine de PaySim."""

import argparse
import csv
import hashlib
import io
import json
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq

from fraud_platform.config import DataPaths
from fraud_platform.eda import SCHEMA
from fraud_platform.silver import clean_transaction

BATCH_SIZE = 50_000
MONEY = pa.decimal128(38, 12)
SILVER_TYPES = {int: pa.int64(), float: MONEY, str: pa.string()}
PROVENANCE = [
    ("source_sha256", pa.string()),
    ("source_record", pa.int64()),
    ("transaction_id", pa.string()),
]
BRONZE = pa.schema([(name, pa.string()) for name in SCHEMA] + PROVENANCE)
SILVER = pa.schema([
    (name, pa.bool_() if name in ("isFraud", "isFlaggedFraud") else SILVER_TYPES[kind])
    for name, kind in SCHEMA.items()
] + PROVENANCE)
QUARANTINE = BRONZE.append(pa.field("rejection_reason", pa.string()))
SCHEMAS = {"bronze": BRONZE, "silver": SILVER, "quarantine": QUARANTINE}


def build_layers(source: Path, paths: DataPaths) -> dict[str, int]:
    bronze = build_bronze(source, paths)
    counts = build_silver(bronze, paths)
    return {"bronze": counts["silver"] + counts["quarantine"], **counts}


def build_bronze(source: Path, paths: DataPaths) -> Path:
    """Conserve les valeurs CSV brutes et leur provenance dans un Parquet."""
    paths.create()
    with source.open("rb") as binary, TemporaryDirectory(dir=paths.root) as staging:
        digest = hashlib.file_digest(binary, "sha256").hexdigest()
        binary.seek(0)
        filename = f"{digest}.parquet"
        temporary = Path(staging) / filename
        batch = []
        with ExitStack() as stack:
            stream = stack.enter_context(io.TextIOWrapper(binary, encoding="utf-8-sig", newline=""))
            reader = csv.reader(stream, strict=True)
            if next(reader, None) != list(SCHEMA):
                raise ValueError("En-tête PaySim inattendu")
            writer = stack.enter_context(pq.ParquetWriter(temporary, BRONZE, compression="zstd"))

            for record, row in enumerate(reader, start=1):
                if len(row) != len(SCHEMA):
                    raise ValueError(f"Nombre de colonnes incorrect à l'enregistrement {record}")
                raw = dict(zip(SCHEMA, row, strict=True))
                metadata = {
                    "source_sha256": digest,
                    "source_record": record,
                    "transaction_id": f"{digest}:{record}",
                }
                batch.append(raw | metadata)
                if len(batch) >= BATCH_SIZE:
                    writer.write_table(pa.Table.from_pylist(batch, schema=BRONZE))
                    batch.clear()
            if batch:
                writer.write_table(pa.Table.from_pylist(batch, schema=BRONZE))
        output = paths.bronze / filename
        temporary.replace(output)
    return output


def build_silver(bronze: Path, paths: DataPaths) -> dict[str, int]:
    """Construit Silver et Quarantine exclusivement depuis le Parquet Bronze."""
    paths.create()
    counts = {"silver": 0, "quarantine": 0}
    with TemporaryDirectory(dir=paths.root) as staging, ExitStack() as stack:
        source = stack.enter_context(pq.ParquetFile(bronze))
        if source.schema_arrow != BRONZE:
            raise ValueError("Schéma Bronze inattendu")
        temporary = {name: Path(staging) / f"{name}.parquet" for name in counts}
        writers = {
            name: stack.enter_context(pq.ParquetWriter(temporary[name], SCHEMAS[name], compression="zstd"))
            for name in counts
        }
        for batch in source.iter_batches(batch_size=BATCH_SIZE):
            outputs = {name: [] for name in counts}
            for bronze_row in batch.to_pylist():
                raw = {name: bronze_row[name] for name in SCHEMA}
                metadata = {name: bronze_row[name] for name, _ in PROVENANCE}
                try:
                    cleaned = clean_transaction(raw)
                    if cleaned["step"] >= 2**63:
                        raise ValueError("step: hors plage int64")
                    for column, kind in SCHEMA.items():
                        if kind is float:
                            amount = cleaned[column]
                            if amount.as_tuple().exponent < -12 or amount.adjusted() >= 26:
                                try:
                                    pa.scalar(amount, type=MONEY)
                                except pa.ArrowInvalid as error:
                                    raise ValueError(f"{column}: hors format décimal (38, 12)") from error
                except ValueError as error:
                    outputs["quarantine"].append(bronze_row | {"rejection_reason": str(error)})
                else:
                    outputs["silver"].append(cleaned | metadata)
            for name, rows in outputs.items():
                if rows:
                    writers[name].write_table(pa.Table.from_pylist(rows, schema=SCHEMAS[name]))
                    counts[name] += len(rows)
        stack.close()
        for name, staged in temporary.items():
            staged.replace(getattr(paths, name) / bronze.name)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    print(json.dumps(build_layers(args.csv, DataPaths(args.data_dir)), indent=2))


if __name__ == "__main__":
    main()
