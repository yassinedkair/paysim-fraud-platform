"""Convertit un CSV PaySim et publie ses couches Parquet dans ADLS."""

from airflow.sdk import Param, dag, get_current_context, task


@dag(
    schedule=None,
    catchup=False,
    max_active_runs=1,
    params={"source_file": Param("paysim-smoke.csv", type="string", pattern=r"^[\w-]+\.csv$")},
    tags=["fraud-detection", "adls"],
)
def fraud_detection_ingest():
    @task
    def publish_bronze() -> dict[str, str]:
        import hashlib
        import os
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from azure.core.exceptions import ResourceExistsError
        from azure.identity import EnvironmentCredential
        from azure.storage.blob import BlobServiceClient

        from fraud_platform.config import DataPaths
        from fraud_platform.pipeline import build_bronze

        filename = get_current_context()["params"]["source_file"]
        if Path(filename).name != filename or not filename.endswith(".csv"):
            raise ValueError("Sélectionner le nom d'un CSV dans data/raw")
        source = Path("/fraud-data/raw") / filename
        account = os.environ["ADLS_ACCOUNT_NAME"]
        namespace = "smoke/" if filename == "paysim-smoke.csv" else ""
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        destination = f"{namespace}bronze/{digest}.parquet"
        with TemporaryDirectory() as scratch, EnvironmentCredential() as credential:
            with BlobServiceClient(f"https://{account}.blob.core.windows.net", credential) as service:
                blob = service.get_blob_client(os.environ["ADLS_CONTAINER_NAME"], destination)
                if blob.exists():
                    print(f"Déjà publié : {destination}")
                else:
                    bronze = build_bronze(source, DataPaths(Path(scratch)))
                    if bronze.stem != digest:
                        raise ValueError("La source CSV a changé pendant l'ingestion")
                    try:
                        with bronze.open("rb") as stream:
                            blob.upload_blob(stream, overwrite=False)
                    except ResourceExistsError:
                        print(f"Déjà publié : {destination}")
                    else:
                        print(f"Publié : {destination}")
        return {"bronze_blob": destination, "digest": digest, "namespace": namespace}

    @task
    def publish_silver(source: dict[str, str]) -> dict[str, int]:
        import json
        import os
        from pathlib import Path
        from tempfile import TemporaryDirectory

        import pyarrow.parquet as pq
        from azure.core.exceptions import ResourceExistsError
        from azure.identity import EnvironmentCredential
        from azure.storage.blob import BlobServiceClient

        from fraud_platform.config import DataPaths
        from fraud_platform.pipeline import build_silver
        from fraud_platform.quality import validate_silver

        account = os.environ["ADLS_ACCOUNT_NAME"]
        namespace = source["namespace"]
        with TemporaryDirectory() as scratch, EnvironmentCredential() as credential:
            paths = DataPaths(Path(scratch))
            paths.create()
            bronze = paths.bronze / f"{source['digest']}.parquet"
            with BlobServiceClient(f"https://{account}.blob.core.windows.net", credential) as service:
                container = service.get_container_client(os.environ["ADLS_CONTAINER_NAME"])
                with bronze.open("wb") as stream:
                    container.download_blob(source["bronze_blob"]).readinto(stream)
                print(f"Bronze téléchargé depuis ADLS : {source['bronze_blob']}")
                counts = build_silver(bronze, paths)
                bronze_count = pq.ParquetFile(bronze).metadata.num_rows
                if counts["silver"] + counts["quarantine"] != bronze_count:
                    raise ValueError("Volumes Bronze, Silver et Quarantine incohérents")
                silver, = paths.silver.glob("*.parquet")
                report = validate_silver(silver)
                print(f"Qualité Silver : {json.dumps(report)}")
                report_path = f"{namespace}quality/{silver.stem}.json"
                container.upload_blob(report_path, json.dumps(report), overwrite=True)
                for layer in counts:
                    if layer == "silver" and not report["success"]:
                        continue
                    output, = getattr(paths, layer).glob("*.parquet")
                    destination = f"{namespace}{layer}/{output.name}"
                    try:
                        with output.open("rb") as stream:
                            container.upload_blob(destination, stream, overwrite=False)
                    except ResourceExistsError:
                        print(f"Déjà publié : {destination}")
                    else:
                        print(f"Publié : {destination}")
                if not report["success"]:
                    raise ValueError(f"Validation Silver échouée. Rapport : {report_path}")
        return {"bronze": bronze_count, **counts}

    publish_silver(publish_bronze())


fraud_detection_ingest()
