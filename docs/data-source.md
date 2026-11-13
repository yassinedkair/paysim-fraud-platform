# Source PaySim

- Page de téléchargement indiquée : https://www.kaggle.com/datasets/ealaxi/paysim1
- Téléchargement effectué manuellement par l'utilisateur.
- Fichier reçu et inspecté le 2 novembre 2026.
- Nom original : `PS_20174392719_1491204439457_log.csv`.
- Taille : 493 534 783 octets.
- SHA-256 : `16910f90577b0d981bf8ff289714510bb89bc71bff7d3f220f024e287e4eea6b`.
- Emplacement local : `data/raw/` (exclu de Git).
- Licence indiquée sur Kaggle : CC BY-SA 4.0. Publication par Edgar López-Rojas.

L'empreinte identifie la copie locale. La fiche Kaggle recommande d'exclure
les quatre colonnes de solde des variables du modèle, car le simulateur annule
les transactions détectées comme frauduleuses.

## En-tête observé

```text
step,type,amount,nameOrig,oldbalanceOrg,newbalanceOrig,nameDest,oldbalanceDest,newbalanceDest,isFraud,isFlaggedFraud
```

La présence des colonnes a été vérifiée. Le nombre de lignes, les types et
la qualité de l'ensemble du fichier seront vérifiés lors de l'EDA.
