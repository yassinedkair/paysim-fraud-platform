# Contrat de données PaySim

Le CSV d'origine est la source de référence. Le profilage de la semaine 1
porte sur sa copie identifiée dans [la fiche source](data-source.md).

| Donnée source | Type Silver | Règle |
| --- | --- | --- |
| `step` | Entier | Positif. Représente une heure simulée. |
| `type` | Texte | `CASH_IN`, `CASH_OUT`, `DEBIT`, `PAYMENT` ou `TRANSFER`. |
| `amount`, `oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`, `newbalanceDest` | Décimal (38, 12) | Valeur finie et non négative, représentable sans arrondi. Le CSV analysé contient jusqu'à 12 chiffres après la virgule. |
| `nameOrig`, `nameDest` | Texte | Identifiant non vide. |
| `isFraud`, `isFlaggedFraud` | Booléen | Seules les valeurs source `0` et `1` sont acceptées. |

Une valeur vide est invalide dans chacune des onze colonnes. Un solde à zéro
reste valide. `isFraud` sert de cible et `isFlaggedFraud` reste disponible pour
l'audit. Les quatre colonnes de solde et ces deux indicateurs sont exclus des
entrées du modèle.

## Identité et relance

L'identité technique combine le SHA-256 du CSV et le numéro d'enregistrement
dans ce CSV, en commençant à `1` après l'en-tête. Par exemple, la première
transaction a pour identifiant `<sha256>:1`. Cet identifiant reste identique
si le même fichier est renommé ou retraité. Une modification du CSV change
son empreinte et crée une nouvelle version de la source.

Le numéro d'enregistrement est attribué avant tout filtrage. Une ligne
rejetée garde donc son identifiant et peut être retrouvée dans le fichier
original. Deux lignes identiques situées à des positions différentes ont des
identifiants distincts. Le contrôle des doublons de contenu reste séparé.

## Couches locales

- **Bronze** conserve les onze valeurs brutes en texte et les métadonnées de
  provenance. Une erreur de structure du CSV arrête l'ingestion.
- **Silver** convertit les types et conserve les lignes qui respectent le
  contrat. Les rejets sont isolés avec leur identifiant et leur motif.
- Les sorties sont nommées d'après l'empreinte de la source. Une relance
  remplace les sorties de cette source sans ajouter de lignes aux fichiers
  existants. Les écritures sont préparées dans des fichiers temporaires.
