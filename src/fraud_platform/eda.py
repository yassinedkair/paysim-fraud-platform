"""Profilage reproductible du CSV PaySim original, trié par step."""

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

SCHEMA = {
    "step": int, "type": str, "amount": float, "nameOrig": str,
    "oldbalanceOrg": float, "newbalanceOrig": float, "nameDest": str,
    "oldbalanceDest": float, "newbalanceDest": float,
    "isFraud": int, "isFlaggedFraud": int,
}


def profile(path: Path) -> dict:
    missing = dict.fromkeys(SCHEMA, 0)
    invalid = dict.fromkeys(SCHEMA, 0)
    by_type, by_step, fraud_by_type, fraud_by_step = (Counter() for _ in range(4))
    labels = Counter()
    rows = duplicates = 0
    current_step = None
    seen = set()

    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        if next(reader, None) != list(SCHEMA):
            raise ValueError("En-tête PaySim inattendu")
        for row in reader:
            rows += 1
            if len(row) != len(SCHEMA):
                raise ValueError(f"Nombre de colonnes incorrect à la ligne {reader.line_num}")
            values = {}
            for (name, convert), raw in zip(SCHEMA.items(), row, strict=True):
                if not raw.strip():
                    missing[name] += 1
                    continue
                try:
                    value = convert(raw)
                    if convert is float and not math.isfinite(value):
                        raise ValueError
                    if name in ("isFraud", "isFlaggedFraud") and value not in (0, 1):
                        raise ValueError
                except ValueError:
                    invalid[name] += 1
                    continue
                values[name] = value

            step = values.get("step")
            if step is None or (current_step is not None and step < current_step):
                raise ValueError(f"step absent, invalide ou non trié à la ligne {reader.line_num}")
            if step != current_step:
                seen.clear()
                current_step = step
            key = tuple(row)
            if key in seen:
                duplicates += 1
            seen.add(key)

            kind = values.get("type", "")
            by_type[kind] += 1
            by_step[step] += 1
            label = values.get("isFraud")
            if label is not None:
                labels[label] += 1
            if label == 1:
                fraud_by_type[kind] += 1
                fraud_by_step[step] += 1

    return {
        "rows": rows,
        "expected_types": {name: kind.__name__ for name, kind in SCHEMA.items()},
        "missing": missing,
        "invalid": invalid,
        "exact_duplicates": duplicates,
        "legitimate": labels[0],
        "fraud": labels[1],
        "fraud_rate": labels[1] / labels.total() if labels.total() else None,
        "by_type": dict(by_type),
        "fraud_by_type": dict(fraud_by_type),
        "by_step": dict(by_step),
        "fraud_by_step": dict(fraud_by_step),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = profile(args.csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
