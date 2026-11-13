# Semaine 4 — détection de fraude

## Préparation des données

Le module `fraud_platform.features` lit `gold.fact_transactions` dans la base
locale DuckDB et écrit `data/modeling/transactions.parquet`.

Les entrées du modèle seront `amount`, `transaction_type` et `hour_of_day`.
L'heure dans la journée simulée vaut `(simulation_hour - 1) % 24`. La cible
`is_fraud` indique si la transaction était frauduleuse. Le Parquet conserve
`simulation_hour` et `split` pour vérifier la séparation chronologique.

| Période | Heures simulées | Transactions | Fraudes |
| --- | --- | ---: | ---: |
| Entraînement | 1 à 520 | 6 082 007 | 5 781 |
| Validation | 521 à 631 | 191 147 | 1 180 |
| Test | 632 à 743 | 89 466 | 1 252 |

La séparation repose sur les heures, ce qui garde toutes les transactions
d'une même heure dans la même période. La densité des transactions et la
proportion de fraudes évoluent au cours de la simulation. L'entraînement
ajustera le modèle, la validation servira au choix des réglages et du seuil,
et le test sera réservé à l'évaluation finale.

Depuis la racine du projet, cette commande reconstruit le Parquet et affiche
les compteurs. Elle utilise DuckDB, déjà installé pour la couche Gold.

```powershell
.\.venv\Scripts\python.exe -m fraud_platform.features
```

## Régression logistique

Le pipeline scikit-learn encode les types et les heures par indicateurs.
Il applique `log(1 + amount)` au montant, puis standardise le résultat.
Les transformations sont ajustées sur l'entraînement. La pondération
`class_weight="balanced"` donne à chaque classe le même poids total dans
l'optimisation, ce qui donne davantage de poids à une fraude individuelle.

Ces commandes installent les bibliothèques puis entraînent le modèle depuis
la racine du projet.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[modeling]'
.\.venv\Scripts\python.exe -m fraud_platform.baseline
```

Le modèle et ses transformations sont enregistrés ensemble dans
`artifacts/baseline/logistic_regression.joblib`. Le rapport `validation.json`
contient les métriques de validation. Le seuil de 0,5 fournit une première
mesure. La pondération influence les scores, qui ne sont pas des probabilités
calibrées pour le taux de fraude réel.

Sur 191 147 transactions de validation, la régression logistique a obtenu
une PR-AUC de 0,2399 et une average precision de 0,2407. Au seuil de 0,5,
la précision est de 3,63 %, le rappel de 86,69 % et le F1 de 6,97 %.
La matrice de confusion donne 1 023 fraudes détectées, 157 manquées,
27 142 fausses alertes et 162 825 transactions normales correctement classées.
Le fichier du modèle a été rechargé pour vérifier la prédiction et les 13 tests
Python ont réussi. L'évaluation finale reste réservée au jeu de test.

## LightGBM

LightGBM combine 150 arbres entraînés sur les mêmes heures et les mêmes trois
variables que la régression logistique. Le type de transaction et l'heure dans
la journée sont encodés comme catégories. Le poids des fraudes est calculé en
divisant le nombre de transactions normales par le nombre de fraudes dans
l'entraînement.

Cette commande entraîne LightGBM et enregistre le modèle et le rapport dans
`artifacts/lightgbm/`. La validation utilise les mêmes métriques que la référence.

```powershell
.\.venv\Scripts\python.exe -m fraud_platform.boosted
```

Le premier entraînement pondéré donnait presque uniquement des scores de 0 ou 1
et une average precision de 0,0080. Avec `boost_from_average=False`, LightGBM
part d'un score neutre. Ce réglage a donné 5 056 scores distincts en validation
et les résultats ci-dessous. Les modèles rechargés reproduisent leurs rapports.

| Mesure en validation | Régression logistique | LightGBM |
| --- | ---: | ---: |
| Average precision | 0,2407 | 0,3471 |
| PR-AUC trapézoïdale | 0,2399 | 0,3481 |
| Précision au seuil 0,5 | 3,63 % | 4,36 % |
| Rappel au seuil 0,5 | 86,69 % | 87,37 % |
| F1 au seuil 0,5 | 6,97 % | 8,30 % |
| Fraudes détectées au seuil 0,5 | 1 023 | 1 031 |
| Fausses alertes au seuil 0,5 | 27 142 | 22 630 |

Les 13 tests Python ont réussi. Le jeu de test final reste réservé à
l'évaluation après le choix du modèle et du seuil.

## Seuil d'alerte

Le coût simulé est égal au nombre de fausses alertes plus le nombre de fraudes
manquées multiplié par leur coût relatif. L'unité est le coût d'une fausse
alerte. Ces coûts servent à illustrer la décision dans la démo.

| Coût relatif d'une fraude manquée | Seuil | Fraudes détectées | Fraudes manquées | Fausses alertes |
| ---: | ---: | ---: | ---: | ---: |
| 5 | 0,975015 | 539 | 641 | 647 |
| 20 | 0,895632 | 662 | 518 | 2 282 |
| 100 | 0,631978 | 973 | 207 | 16 242 |

Le scénario de référence utilise le rapport 20 pour 1. Son coût simulé est
de 12 642 unités, contre 25 610 au seuil initial de 0,5 sur la validation.
Le seuil exact est enregistré dans `artifacts/lightgbm/threshold.json`.

Cette commande recalcule les scénarios à partir du modèle LightGBM enregistré
et de la période de validation.

```powershell
.\.venv\Scripts\python.exe -m fraud_platform.threshold
```

## Objectif de rappel et d'erreur globale

L'objectif est de détecter strictement plus de 80 % des fraudes avec au plus
15 % d'erreurs sur l'ensemble des transactions. Le taux d'erreur est la somme
des faux positifs et des faux négatifs divisée par le nombre de transactions.
Le seuil minimisant l'erreur sous ces contraintes sur la validation est
`0.6561001493074923`, enregistré sous `operating_threshold`.

| Période | Fraudes détectées | Fausses alertes | Rappel | Erreur globale |
| --- | ---: | ---: | ---: | ---: |
| Validation | 945 sur 1 180 | 14 298 | 80,08 % | 7,60 % |
| Test au même seuil | 970 sur 1 252 | 7 119 | 77,48 % | 8,27 % |

Le seuil atteint les deux objectifs sur la validation. Sur le test, le rappel
reste inférieur à 80 %. Les résultats du test sont dans `artifacts/lightgbm/test.json`.

Après ce premier test, un seuil avec davantage de marge a été choisi sur la
validation en exigeant plus de 85 % de rappel et au plus 15 % d'erreurs.
Le seuil candidat `0.5617293409892409` atteint 85,08 % de rappel et 10,60 %
d'erreur globale sur la validation. Sur le test déjà consulté, il atteint
82,35 % de rappel et 11,46 % d'erreur globale. Ce second résultat est un
diagnostic à confirmer sur une nouvelle période indépendante. Le détail est
enregistré dans `artifacts/lightgbm/threshold_margin.json`.

## Seuil retenu pour la démonstration

L'objectif supplémentaire de manquer au plus 10 % des fraudes a été exploré.
Sur la validation, atteindre 90 % de rappel exige au minimum 15,09 % d'erreurs
globales. Maximiser le rappel sous le plafond de 15 % donne le seuil
`0.39133504222476395`, avec 89,92 % de rappel et 14,97 % d'erreurs. Sur la
période de test déjà consultée, ce seuil donne 87,70 % de rappel et 16,92 %
d'erreurs. Le détail est dans `artifacts/lightgbm/threshold_error_cap.json`.

Le seuil de démonstration reste `0.5617293409892409`. Il respecte le plafond
sur les deux périodes mesurées et atteint 82,35 % de rappel sur la seconde.
Le taux de fraudes manquées sur cette période est de 17,65 %. Une confirmation
sur de nouvelles données reste nécessaire.

## Expériences MLflow et explications SHAP

Ces commandes installent MLflow, calculent les explications LightGBM, puis
enregistrent les deux modèles et leurs rapports dans une expérience locale.
Elles réutilisent les modèles entraînés et le seuil fixé pour la démonstration.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[modeling,tracking]'
.\.venv\Scripts\python.exe -m fraud_platform.explain
.\.venv\Scripts\python.exe -m fraud_platform.tracking
```

MLflow conserve les paramètres, métriques et chemins des fichiers dans
`artifacts/mlflow/tracking.db`. Les modèles et rapports sont copiés dans
`artifacts/mlflow/runs/`. La mesure sur le test réutilisé porte le préfixe
`demo_reused_test_`.

Cette commande ouvre un serveur MLflow local pour comparer les deux runs dans
l'expérience `fraud-detection-paysim` à l'adresse `http://127.0.0.1:5000`.

```powershell
.\.venv\Scripts\mlflow.exe server --backend-store-uri sqlite:///artifacts/mlflow/tracking.db --host 127.0.0.1 --port 5000
```

SHAP utilise les contributions calculées par LightGBM sur un échantillon de
validation. Les contributions positives augmentent le score brut, les
négatives le diminuent. Le graphique utilise la valeur absolue moyenne pour
montrer l'ampleur des effets dans l'échantillon. Le rapport JSON contient
aussi les contributions signées d'une transaction fictive. La somme des
contributions et de la valeur de référence, passée par la fonction logistique,
reproduit le score du modèle.

Les runs `logistic_regression` et `lightgbm` ont été relus dans SQLite après
enregistrement. LightGBM conserve le seuil exact `0.5617293409892409`, le
rapport de décision et les deux fichiers SHAP. Sur 2 000 transactions de
validation, le type domine les contributions absolues moyennes. Le transfert
fictif de 500 à l'heure 0 obtient un score de 0,985. Le type, l'heure et le
montant augmentent tous le score brut de cet exemple. Les contributions
reconstruisent les 2 001 scores vérifiés et les 16 tests Python passent.
