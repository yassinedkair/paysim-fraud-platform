"""Validation et conversion d'une transaction brute pour Silver."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from fraud_platform.eda import SCHEMA

TRANSACTION_TYPES = {"CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"}


def clean_transaction(raw: Mapping[str, str]) -> dict[str, int | str | Decimal | bool]:
    """Retourne les valeurs typées ou lève ValueError avec le premier motif de rejet."""
    cleaned = {}
    for column, source_type in SCHEMA.items():
        value = raw.get(column, "").strip()
        if not value:
            raise ValueError(f"{column}: valeur manquante")

        if column == "step":
            try:
                step = int(value)
            except ValueError as error:
                raise ValueError("step: entier attendu") from error
            if step <= 0:
                raise ValueError("step: entier strictement positif attendu")
            cleaned[column] = step
        elif column in ("isFraud", "isFlaggedFraud"):
            if value not in {"0", "1"}:
                raise ValueError(f"{column}: 0 ou 1 attendu")
            cleaned[column] = value == "1"
        elif source_type is float:
            try:
                amount = Decimal(value)
            except InvalidOperation as error:
                raise ValueError(f"{column}: nombre décimal attendu") from error
            if not amount.is_finite() or amount < 0:
                raise ValueError(f"{column}: nombre fini et non négatif attendu")
            cleaned[column] = amount
        else:
            if column == "type" and value not in TRANSACTION_TYPES:
                raise ValueError("type: type de transaction inconnu")
            cleaned[column] = value

    return cleaned
