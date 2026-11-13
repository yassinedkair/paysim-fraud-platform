from decimal import Decimal

import pytest

from fraud_platform.silver import clean_transaction


@pytest.fixture
def transaction():
    return {
        "step": "1", "type": "PAYMENT", "amount": "100.00",
        "nameOrig": "C1", "oldbalanceOrg": "150", "newbalanceOrig": "50",
        "nameDest": "M1", "oldbalanceDest": "0", "newbalanceDest": "0",
        "isFraud": "0", "isFlaggedFraud": "1",
    }


def test_valid_transaction_is_converted(transaction):
    cleaned = clean_transaction(transaction)
    assert cleaned["step"] == 1
    assert isinstance(cleaned["amount"], Decimal)
    assert cleaned["amount"] == Decimal("100.00")
    assert cleaned["oldbalanceDest"] == Decimal("0")
    assert cleaned["isFraud"] is False
    assert cleaned["isFlaggedFraud"] is True


@pytest.mark.parametrize("column,value", [
    ("step", "0"), ("type", "UNKNOWN"), ("amount", "-50"),
    ("amount", "NaN"), ("nameDest", " "), ("isFraud", "2"),
])
def test_invalid_transaction_reports_the_column(transaction, column, value):
    transaction[column] = value
    with pytest.raises(ValueError, match=f"^{column}:"):
        clean_transaction(transaction)
