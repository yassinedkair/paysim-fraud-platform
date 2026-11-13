# Semaine 1 — fondations

## État

- [x] Structure Python et configuration des chemins locaux.
- [x] Protection Git des secrets et données.
- [x] Tests de séparation des couches et de conservation des données.
- [x] Initialiser Git et créer le dépôt GitHub.
- [x] Télécharger PaySim, relever sa licence et enregistrer son SHA-256.
- [x] EDA : volumes, types, valeurs manquantes, doublons, déséquilibre et distribution temporelle.
- [x] Définir le [contrat de données et une identité stable des transactions](data-contract.md).
- [x] Construire Bronze puis Silver en Parquet avec relance sans doublons.
- [x] Ajouter les tests d'ingestion et de transformation.
- [x] Vérifier le seuil de 30 USD sur les coûts réels du groupe `rg-fraud-detection` dans le portail Azure.
- [x] Créer le compte ADLS Gen2 `stfrauddetection1234` et vérifier l'envoi et le téléchargement de `adls-test.txt` dans `fraud-data` depuis le portail.

Le destinataire de l'alerte a été confirmé dans **Edit budget**. Le budget Azure se réinitialise chaque année. Le suivi des 30 USD sur toute la durée du projet doit cumuler les périodes.

L'arrêt automatique de l'API sur alerte sera configuré et testé lors de son déploiement en semaine 5. Les données et le stockage feront l'objet d'une décision manuelle.

## Résultats de l'EDA

Le fichier contient 6 362 620 transactions sur 743 heures simulées. Parmi elles,
8 213 sont étiquetées comme fraudes, soit 0,1291 %. Les fraudes observées se
répartissent entre `CASH_OUT` (4 116) et `TRANSFER` (4 097).

Le profilage n'a trouvé aucun champ vide, aucune valeur incompatible avec les
types vérifiés et aucun doublon exact sur les 11 colonnes. Les totaux par heure
ont été rapprochés des totaux globaux. La commande du README reproduit le
rapport détaillé dans `artifacts/eda/paysim.json`.

## Résultats du pipeline local

Les métadonnées Parquet confirment 6 362 620 lignes dans Bronze et Silver et
zéro rejet dans Quarantine. Silver conserve les montants en décimal et les
indicateurs de fraude en booléen. Les 11 tests passent, dont une relance sur
un échantillon qui vérifie les identifiants et l'absence de lignes ajoutées.

## Critère de fin

Une source identifiée et vérifiée, une EDA reproductible, des couches locales
Bronze/Silver reproductibles, des tests réussis, un dépôt sans secrets et un
stockage ADLS vérifié avec suivi du budget. La semaine 2 commence seulement ensuite.
