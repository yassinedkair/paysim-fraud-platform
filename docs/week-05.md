# Semaine 5 — API de détection de fraude

Au démarrage, FastAPI charge le modèle LightGBM et le seuil de démonstration
depuis `artifacts/lightgbm/`. La variable `FRAUD_MODEL_DIR` permet de choisir
un autre dossier contenant `lightgbm.joblib` et `threshold_margin.json`.

| Route | Fonction |
| --- | --- |
| `GET /health` | Confirme que le service a démarré. |
| `GET /model-info` | Donne le nom du modèle, ses entrées et son seuil. |
| `POST /predict` | Valide la transaction, calcule son score et décide si une alerte est nécessaire. |

Depuis la racine, installe les dépendances de l'API et du modèle.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[modeling,api,dev]'
```

Cette commande démarre l'API localement. L'interface de test est accessible
sur `http://127.0.0.1:8000/docs`.

```powershell
.\.venv\Scripts\python.exe -m uvicorn fraud_platform.api:app --host 127.0.0.1 --port 8000
```

Dans l'interface, utilise **Try it out** sur `POST /predict` avec cet exemple.

```json
{"amount": 500, "transaction_type": "TRANSFER", "hour_of_day": 0}
```

Le champ `alert` vaut `true` si le score atteint ou dépasse le seuil. Le score
sert à classer le risque et n'est pas une probabilité de fraude calibrée.

## Étapes restantes

- [x] Construire l'image Docker et vérifier les trois routes dans le conteneur.
- [x] Ouvrir la démo de l'API Docker sur le poste local.
- [ ] Configurer GitHub Actions pour les tests Python et dbt, puis vérifier la construction de l'image.
- [ ] Finaliser la documentation de la démonstration locale.

La démo utilise l'image Docker locale pour éviter le coût récurrent d'ACR.
Le déploiement Container Apps et son arrêt sur alerte sont reportés à une
éventuelle version hébergée. Les couches de données restent sur ADLS Gen2.

Une fois ces étapes validées, la semaine 6 ajoutera trois extensions.

- **Terraform** pour décrire et reproduire la configuration Azure.
- **NLP sur les réclamations CFPB** pour construire `fact_reclamations` et entraîner un modèle de classification.
- **Evidently** pour comparer les distributions des données et des scores entre périodes, puis mesurer les performances quand les labels sont disponibles.

## Reproduire le test Docker

Depuis la racine, construis l'image avec `Dockerfile.api`. Le contexte de
construction inclut le code Python, la configuration et les deux fichiers du
modèle. La seconde commande démarre le conteneur et expose l'interface sur
`http://127.0.0.1:8000/docs` si ce port est libre.

```powershell
docker build -f Dockerfile.api -t fraud-detection-api:local .
docker run --rm -p 127.0.0.1:8000:8000 fraud-detection-api:local
```

Le test HTTP a confirmé les trois routes. Le transfert de 500 à l'heure 0
renvoie un score de `0.9849980921933834` au seuil `0.5617293409892409`, avec
`alert: true`. Un montant négatif renvoie HTTP 422.

## Intégration continue

Le workflow `.github/workflows/ci.yml` se lance sur les pushes et les pull
requests. Il exécute pytest, génère 720 transactions fictives et les traite
avec le pipeline Bronze et Silver. Il construit et teste Gold avec dbt,
entraîne un LightGBM sur ces données, puis teste les trois routes HTTP de
l'image Docker. Aucun identifiant Azure n'est requis.

Dans GitHub, l'onglet **Actions** affiche le résultat de chaque étape après
le push du workflow. Le modèle de CI sert au test de construction. La démo
locale utilise le modèle entraîné sur PaySim et son seuil vérifié.
