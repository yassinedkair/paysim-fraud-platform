import pytest

pd = pytest.importorskip('pandas')
pytest.importorskip('sklearn')
pytest.importorskip('duckdb')

from fraud_platform.ieee_experiment import chronological_split, feature_frame, load_data


def test_temporal_split_keeps_tied_times_together_and_excludes_target():
    data = pd.DataFrame({'TransactionID': range(200), 'TransactionDT': [i // 2 for i in range(200)],
                         'isFraud': [bool(i % 2) for i in range(200)],
                         'TransactionAmt': 50., 'DeviceInfo': None})
    train, validation, test = chronological_split(data)
    assert train.TransactionDT.max() < validation.TransactionDT.min()
    assert validation.TransactionDT.max() < test.TransactionDT.min()
    assert len(train) + len(validation) + len(test) == len(data)
    features = feature_frame(train)
    assert not {'isFraud', 'TransactionID', 'TransactionDT'}.intersection(features.columns)
    assert features.DeviceInfo.eq('__MISSING__').all()


def test_identity_join_preserves_unmatched_transactions_and_rejects_duplicates(tmp_path):
    pd.DataFrame({'TransactionID': [1, 2], 'TransactionDT': [1, 2],
                  'isFraud': [0, 1], 'TransactionAmt': [50, 100]}).to_csv(tmp_path / 'train_transaction.csv', index=False)
    identities = pd.DataFrame({'TransactionID': [1], 'DeviceInfo': ['phone']})
    identities.to_csv(tmp_path / 'train_identity.csv', index=False)
    data = load_data(tmp_path)
    assert len(data) == 2
    assert pd.isna(data.loc[1, 'DeviceInfo'])
    pd.concat([identities, identities]).to_csv(tmp_path / 'train_identity.csv', index=False)
    with pytest.raises(pd.errors.MergeError):
        load_data(tmp_path)


def test_enhanced_features_do_not_depend_on_fraud_labels():
    data = pd.DataFrame({'TransactionID': [1, 2], 'TransactionDT': [86400, 172800],
                         'isFraud': [False, True], 'TransactionAmt': [12.5, 14.],
                         'card1': ['a', 'b'], 'card2': ['c', None], 'addr1': ['x', 'y'],
                         **{column: [1., 2.] for column in ('D1', 'D2', 'D4', 'D10', 'D15')}})
    expected = feature_frame(data, enhanced=True)
    data['isFraud'] = ~data.isFraud
    pd.testing.assert_frame_equal(expected, feature_frame(data, enhanced=True))
