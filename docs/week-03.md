# Semaine 3 — couche Gold

DuckDB lit le Parquet Silver et stocke les tables analytiques dans le fichier
local `data/gold/fraud.duckdb`. dbt exécute les modèles SQL dans l'ordre de
leurs dépendances et lance les tests associés.

| Modèle | Contenu |
| --- | --- |
| `stg_transactions` | Vue sur le Parquet Silver avec les noms analytiques des colonnes. |
| `fact_transactions` | Une ligne par transaction, avec son montant, son heure simulée et sa cible de fraude. |
| `dim_date` | Une ligne par jour simulé. Les heures 1 à 24 appartiennent au jour 1. |
| `dim_transaction_type` | Une ligne par type de transaction observé. |

Les dimensions utilisent le numéro de jour et le type comme clés. PaySim fournit
des heures simulées, et le modèle les regroupe par périodes de 24 heures.

Depuis la racine, installe les dépendances analytiques dans `.venv`.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[analytics]'
```

Crée le dossier de sortie s'il manque, puis construis et teste Gold.

```powershell
New-Item -ItemType Directory -Force data/gold
.\.venv\Scripts\dbt.exe build --project-dir dbt --profiles-dir dbt
```

Par défaut, dbt lit la copie locale du Parquet Silver complet. Pour une autre
copie, définis `FRAUD_SILVER_PATH` avec le chemin d'un seul fichier Parquet.
Les tests contrôlent l'unicité, les valeurs obligatoires, les liens vers les
dimensions et la conservation du volume, du nombre de fraudes et du montant
total de Silver.

La requête suivante utilise les deux dimensions pour compter les transactions
et les fraudes par jour et type.

```sql
select
    d.simulation_day,
    t.transaction_type,
    count(*) as transactions,
    count_if(f.is_fraud) as frauds
from gold.fact_transactions as f
join gold.dim_date as d using (simulation_day)
join gold.dim_transaction_type as t using (transaction_type)
group by d.simulation_day, t.transaction_type
order by d.simulation_day, t.transaction_type;
```

Le 11 novembre 2026, `dbt build` a créé une vue et trois tables sur le fichier
Silver complet. Les 14 tests ont réussi. Une lecture directe de DuckDB a
confirmé 6 362 620 transactions, dont 8 213 fraudes, 31 jours simulés et 5 types.
L'exécution a utilisé dbt Core 1.12.6, dbt-duckdb 1.11.1 et DuckDB 2.0.0.

## Publication Gold dans Azure

Les trois tables ont été exportées avec `COPY ... (FORMAT PARQUET, COMPRESSION ZSTD)`
dans `data/gold/parquet/`. Le nombre de lignes dans les métadonnées de chaque
Parquet a été comparé à celui de sa table DuckDB. Les fichiers ont été envoyés
dans `fraud-data` avec l'identité Microsoft Entra d'Airflow. Les tailles et les
empreintes MD5 enregistrées dans Azure correspondent aux fichiers locaux.

| Chemin dans `fraud-data` | Lignes | Taille en octets |
| --- | ---: | ---: |
| `gold/fact_transactions.parquet` | 6 362 620 | 53 331 770 |
| `gold/dim_date.parquet` | 31 | 290 |
| `gold/dim_transaction_type.parquet` | 5 | 302 |

Dans le portail Azure, ouvre le compte `stfrauddetection1234`, puis **Containers**,
**fraud-data** et le dossier **gold**.

## Azure Key Vault

Le coffre Standard `kv-fraud-detection-1234` est dans `rg-fraud-detection`.
Azure RBAC attribue `Key Vault Secrets Officer` au compte utilisateur pour
gérer les secrets et `Key Vault Secrets User` à `airflow-fraud-detection-local`
pour lire leurs valeurs. Un conteneur Airflow temporaire a obtenu un jeton
Microsoft Entra pour Key Vault et lu `fraud-platform-test`. Le test a confirmé
la valeur fictive. L'identité Airflow s'authentifie avec le secret déjà conservé
dans `.env` hors de Git.
