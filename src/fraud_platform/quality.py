"""Contrôle Great Expectations des Parquet Silver par lots."""

from pathlib import Path

import great_expectations as gx
import pyarrow.parquet as pq

from fraud_platform.silver import TRANSACTION_TYPES

COLUMNS = ["transaction_id", "step", "type", "amount", "isFraud"]


def validate_silver(path: Path) -> dict[str, object]:
    context = gx.get_context(mode="ephemeral")
    context.variables.progress_bars = {"globally": False}
    source = context.data_sources.add_pandas(name="paysim")
    asset = source.add_dataframe_asset(name="silver")
    batch = asset.add_batch_definition_whole_dataframe(name="parquet_batch")
    suite = context.suites.add(gx.ExpectationSuite(name="paysim_silver"))
    for column in COLUMNS:
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="transaction_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="step", min_value=1))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeInSet(
        column="type", value_set=sorted(TRANSACTION_TYPES)
    ))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="amount", min_value=0))
    validation = context.validation_definitions.add(gx.ValidationDefinition(
        name="validate_silver", data=batch, suite=suite
    ))

    rows = batches = 0
    failures = []
    with pq.ParquetFile(path) as parquet:
        for record_batch in parquet.iter_batches(batch_size=50_000, columns=COLUMNS):
            batches += 1
            rows += record_batch.num_rows
            result = validation.run(
                batch_parameters={"dataframe": record_batch.to_pandas()},
                result_format="BOOLEAN_ONLY",
            )
            for check in result.results:
                if not check.success:
                    config = check.expectation_config
                    failures.append({"batch": batches, "check": config.type, "column": config.kwargs.get("column")})
    return {
        "suite": "paysim_silver", "success": batches > 0 and not failures,
        "rows": rows, "batches": batches, "checks_per_batch": len(suite.expectations),
        "failures": failures,
    }
