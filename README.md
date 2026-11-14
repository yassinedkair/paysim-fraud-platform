# Plateforme de détection de fraude

Pipeline de données et API de scoring construits sur **PaySim**, un jeu de transactions financières simulées. Le projet couvre l’ingestion et le contrôle qualité, la modélisation SQL, l’entraînement et l’explication d’un modèle, puis sa mise à disposition dans une API locale.

| Composant | Rôle |
| --- | --- |
| Airflow, Azure ADLS Gen2 et Great Expectations | Ingestion du CSV, publication de Bronze, validation de Silver et mise en quarantaine des rejets |
| dbt et DuckDB | Construction et tests du modèle Gold avec les transactions, les jours simulés et les types de transaction |
| scikit-learn, LightGBM, MLflow et SHAP | Comparaison des modèles, suivi des expériences et explication des scores |
| FastAPI et Docker | Scoring local et décision d’alerte à partir du montant, du type et de l’heure simulée |
| GitHub Actions | Vérification automatique des tests Python et dbt, puis construction et test HTTP du conteneur |

## Exécution locale

Les commandes s’exécutent dans **PowerShell**, à la racine du dépôt. Il faut Python 3.13 et Docker Desktop pour la démo conteneurisée.

### 1. Préparer les données

Crée l’environnement Python si nécessaire et installe les dépendances.

```powershell
py -3.13 -m venv .venv
$python = '.\.venv\Scripts\python.exe'
& $python -m pip install -e '.[analytics,modeling,api,dev,tracking]'
```

Télécharge le CSV PaySim décrit dans la [fiche source](docs/data-source.md) et place-le dans `data/raw/`. Les commandes suivantes créent les Parquet Bronze et Silver, construisent les tables Gold et préparent les jeux chronologiques du modèle.

```powershell
$source = 'data/raw/PS_20174392719_1491204439457_log.csv'
& $python -m fraud_platform.pipeline $source
$sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
$env:FRAUD_SILVER_PATH = "data/silver/$sha.parquet"
.\.venv\Scripts\dbt.exe build --project-dir dbt --profiles-dir dbt
& $python -m fraud_platform.features
```

### 2. Entraîner le modèle

L’entraînement écrit le modèle et ses métriques de validation dans `artifacts/`. Pour reproduire la démo, le bloc suivant enregistre le seuil fixé lors des expériences.

```powershell
& $python -m fraud_platform.baseline
& $python -m fraud_platform.boosted
if (-not (Test-Path artifacts/lightgbm/threshold_margin.json)) {
    '{"validation":{"threshold":0.5617293409892409}}' |
        Set-Content -Encoding ascii artifacts/lightgbm/threshold_margin.json
}
```

### 3. Lancer l’API

Démarre l’API avec l’une des deux méthodes ci-dessous.

```powershell
& $python -m uvicorn fraud_platform.api:app --host 127.0.0.1 --port 8000
```

```powershell
docker build -f Dockerfile.api -t fraud-detection-api:local .
docker run --rm -p 127.0.0.1:8000:8000 fraud-detection-api:local
```

Ouvre [Swagger](http://127.0.0.1:8000/docs). Dans **POST /predict**, clique sur **Try it out**, saisis la transaction suivante et clique sur **Execute**.

```json
{"amount": 500, "transaction_type": "TRANSFER", "hour_of_day": 0}
```

L’API renvoie le score, le seuil et la décision `alert`. Le score sert à classer les transactions par risque. `GET /health` vérifie la disponibilité du service et `GET /model-info` affiche le modèle et son seuil.

### 4. Vérifier le projet

```powershell
& $python -m pytest -q
```

Le [workflow GitHub Actions](.github/workflows/ci.yml) utilise des transactions fictives pour vérifier le parcours jusqu’à l’API Docker.

## Exécution avec Airflow et Azure

Copie [`.env.example`](.env.example) vers `.env` si ce dernier n’existe pas. Renseigne les paramètres Airflow et ceux de l’identité Microsoft Entra autorisée à lire et écrire dans le conteneur ADLS. Prépare le compte ADLS Gen2 et le conteneur privé avant de lancer le DAG. Les valeurs sensibles restent dans `.env`, ignoré par Git.

```powershell
docker compose build airflow-worker
docker compose up airflow-init
docker compose up -d
```

Dans [Airflow](http://127.0.0.1:8081), déclenche `fraud_detection_ingest` avec le nom du CSV local dans le paramètre `source_file`. Le DAG publie Bronze, le relit depuis ADLS pour produire Silver, puis publie les rejets et le rapport qualité.

## Extensions

- **SHAP**. Après l’entraînement, exécute `python -m fraud_platform.explain` avec l’environnement du projet. Le rapport et le graphique sont générés dans `artifacts/lightgbm/`.
- **NLP CFPB**. Décompresse un export de [l’archive des récits CFPB](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/) dans `data/raw/cfpb-narratives.csv`, puis exécute `python -m fraud_platform.complaints data/raw/cfpb-narratives.csv`. Le Parquet, le modèle et les métriques sont écrits dans `data/complaints/`.
- **Terraform**. Le module [`infra/`](infra/) décrit le groupe, le stockage ADLS et Key Vault. Pour vérifier la configuration, exécute `terraform -chdir=infra init -backend=false` puis `terraform -chdir=infra validate`.
- **Evidently**. Le module `fraud_platform.monitoring` produit les rapports de dérive dans `artifacts/monitoring/`. Pour Evidently 0.7, utilise pandas 2.3.3 dans un environnement dédié avec les extras `modeling,monitoring`, puis exécute `python -m fraud_platform.monitoring`.

[Source PaySim](docs/data-source.md) · [Contrat de données](docs/data-contract.md)
