"""Vérifie l'exécution locale d'un DAG Airflow."""

from airflow.sdk import dag, task


@dag(schedule=None, catchup=False, tags=["fraud-detection", "smoke-test"])
def fraud_detection_smoke():
    @task
    def prepare_message() -> str:
        return "Airflow local OK"

    @task
    def verify_message(message: str) -> None:
        if message != "Airflow local OK":
            raise ValueError(f"Message inattendu : {message!r}")
        print(message)

    verify_message(prepare_message())


fraud_detection_smoke()
