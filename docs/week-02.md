# Semaine 2 — Airflow local

Le fichier `docker-compose.yaml` part du [guide Airflow 3.3.2](https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/docker-compose/index.html). L'interface écoute sur `127.0.0.1:8081`, le port 8080 ayant provoqué un conflit local.

| Service | Rôle |
| --- | --- |
| PostgreSQL | Conserve l'état des DAG et des exécutions. |
| Redis | Transmet les tâches aux workers. |
| API server | Sert l'interface Web et l'API Airflow. |
| Scheduler et DAG processor | Lisent les DAG et planifient les tâches. |
| Worker | Exécute les tâches planifiées. |
| Triggerer | Attend les événements pour les tâches qui savent se mettre en attente. |

Le fichier `.env` local contient les paramètres de connexion et la clé Fernet
qui sert à chiffrer les secrets stockés par Airflow. Il est ignoré par Git.

Depuis PowerShell à la racine, cette commande initialise la base et crée le
compte Airflow configuré dans `.env`.

```powershell
docker compose build airflow-worker
docker compose up airflow-init
```

Après une initialisation réussie, cette commande démarre les services en arrière-plan.

```powershell
docker compose up -d
```

Cette commande affiche l'état des services.

```powershell
docker compose ps
```

L'interface est disponible sur `http://127.0.0.1:8081` avec le compte `airflow`
et le mot de passe local `_AIRFLOW_WWW_USER_PASSWORD` du fichier `.env`.

## Test de démarrage

Le DAG `fraud_detection_smoke` se lance manuellement. `prepare_message` produit
un message, puis `verify_message` le contrôle. Le lancement dans le portail
Airflow a été effectué par l'utilisateur. Deux tâches vertes et le message
`Airflow local OK` dans les logs confirment le test.

## Connexion au stockage Azure

Le pipeline cible le conteneur privé `fraud-data` du compte
`stfrauddetection1234`. Le worker Airflow local doit disposer d'une identité
Microsoft Entra autorisée à lire et écrire dans ce conteneur. Les identifiants
d'authentification restent dans l'environnement local et hors de Git.

## DAG d'ingestion

`fraud_detection_ingest` se déclenche à la demande. Le paramètre `source_file`
désigne le nom d'un CSV dans `data/raw/`, accessible au worker en lecture seule.
`publish_bronze` convertit le CSV en Parquet Bronze et le publie dans Azure.
Si ce Bronze existe déjà, il est réutilisé. `publish_silver` télécharge ce
Bronze depuis ADLS, applique le nettoyage et contrôle Silver avant publication.
Le SHA-256 du CSV détermine le nom de chaque fichier.
Une relance conserve les fichiers déjà présents à ces chemins.

Le test utilise `paysim-smoke.csv`, deux transactions fictives dont une avec un
montant négatif. Les sorties attendues sous `smoke/` sont deux lignes Bronze,
une ligne Silver et une ligne en quarantaine. Le pipeline applique la validation
Python de la semaine 1. Great Expectations contrôle ensuite Silver par lots
de 50 000 lignes maximum, avec neuf vérifications par lot. L'unicité est
contrôlée au sein de chaque lot. Le rapport JSON est écrit sous `quality/`
(ou `smoke/quality/` pour le test). Si le rapport indique un échec, la
publication de Silver est bloquée. Les rejets et le rapport restent disponibles.

Le 9 novembre 2026, le rapport `smoke/quality/d9c0352aecc3b0da6eaa73ad7f1e056dfeafbb51395b23e246213aeadcac25ab.json`
a été relu depuis Azure avec l'identité Airflow. Il confirme `success: true`,
une ligne Silver, un lot, neuf contrôles et zéro échec. La relance de
l'échantillon conserve les trois Parquet existants. Le réglage qui désactive
les barres de progression a passé un test dans un conteneur temporaire.
Ce réglage est désormais intégré à l'image du worker.

## Exécution du CSV complet

L'exécution `full_paysim_20261109` s'est terminée avec succès le 9 novembre
2026 en 44 min 17 s. Les logs confirment 6 362 620 lignes Bronze, autant dans
Silver, zéro rejet et la publication des trois fichiers Parquet dans Azure.
Great Expectations a validé 128 lots avec neuf contrôles par lot et zéro
échec. Le rapport porte sur les 6 362 620 lignes Silver.

## Validation du découpage Bronze vers Silver

L'exécution `split_smoke_20261109` a validé les deux tâches sur l'échantillon.
Les logs confirment le téléchargement de Bronze depuis ADLS, la réussite des
neuf contrôles qualité et les compteurs 2 Bronze, 1 Silver, 1 rejet. Les fichiers
existants ont été réutilisés. Les 12 tests Python passent, dont la construction
de Silver depuis Bronze après suppression du CSV de test. L'exécution complète
ci-dessus utilisait la version précédente à une seule tâche.

## Validation finale de la semaine 2

L'exécution complète `split_full_paysim_20261109` a réussi. Les logs confirment
la réutilisation de Bronze, son téléchargement depuis ADLS par `publish_silver`,
6 362 620 lignes Silver et zéro rejet. Great Expectations a validé 128 lots de
neuf contrôles chacun, sans échec. Les sorties existantes ont été reconnues
sans doublons. Le rapport qualité a été actualisé dans Azure.

Les semaines 1 et 2 sont validées. La prochaine étape est la couche Gold avec
dbt et DuckDB, puis ses tests et sa documentation.
