"""Compare LightGBM et CatBoost sur une séparation chronologique IEEE-CIS."""

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from fraud_platform.baseline import evaluate_scores
from fraud_platform.threshold import choose_balanced_threshold


CATEGORICAL = {
    'ProductCD', 'P_emaildomain', 'R_emaildomain', 'DeviceType', 'DeviceInfo',
    'addr1', 'addr2', *(f'card{i}' for i in range(1, 7)),
    *(f'M{i}' for i in range(1, 10)), *(f'id_{i}' for i in range(12, 39)),
}


def load_data(directory):
    frames = []
    for filename in ('train_transaction.csv', 'train_identity.csv'):
        path = directory / filename
        columns = pd.read_csv(path, nrows=0).columns
        dtypes = {column: 'str' if column in CATEGORICAL else 'float32' for column in columns}
        dtypes['TransactionID'] = 'int64'
        if 'TransactionDT' in columns:
            dtypes['TransactionDT'] = 'int64'
        frames.append(pd.read_csv(path, dtype=dtypes))
    transactions, identities = frames
    if transactions.TransactionID.isna().any() or transactions.TransactionID.duplicated().any():
        raise ValueError('TransactionID invalide ou dupliqué')
    data = transactions.merge(identities, on='TransactionID', how='left', validate='one_to_one')
    if not data.isFraud.isin([0, 1]).all():
        raise ValueError('isFraud doit valoir 0 ou 1')
    if data.TransactionDT.isna().any():
        raise ValueError('TransactionDT manquant')
    data['isFraud'] = data.isFraud.astype(bool)
    return data.sort_values(['TransactionDT', 'TransactionID']).reset_index(drop=True)


def chronological_split(data):
    """Garde toutes les transactions d'un même instant dans la même période."""
    times = data.TransactionDT.sort_values().to_numpy()
    first, second = times[int(len(times) * .70)], times[int(len(times) * .85)]
    partitions = (
        data[data.TransactionDT < first].copy(),
        data[data.TransactionDT.between(first, second, inclusive='left')].copy(),
        data[data.TransactionDT >= second].copy(),
    )
    for part in partitions:
        if part.empty or part.isFraud.nunique() != 2:
            raise ValueError('Chaque période doit contenir les deux classes')
    return partitions


def feature_frame(data, enhanced=False):
    raw = data.drop(columns=['TransactionID', 'TransactionDT', 'isFraud'], errors='ignore')
    result = raw.copy()
    result['hour'] = (data.TransactionDT // 3600 % 24).astype('float32')
    result['day_in_week'] = (data.TransactionDT // 86400 % 7).astype('float32')
    for column in result.columns.intersection(list(CATEGORICAL)):
        result[column] = result[column].fillna('__MISSING__').astype(str)
    if enhanced:
        for column in ('D1', 'D2', 'D4', 'D10', 'D15'):
            result[f'{column}_origin_day'] = (data.TransactionDT / 86400 - data[column]).astype('float32')
        result['amount_fraction'] = (data.TransactionAmt % 1).astype('float32')
        result['missing_fields'] = raw.isna().sum(axis=1).astype('float32')
        result['card_address'] = result['card1'] + '_' + result['card2'] + '_' + result['addr1']
    return result


def metrics(labels, scores, threshold, target=.8):
    report = evaluate_scores(labels, scores, threshold)
    report['rows'] = report.pop('validation_rows')
    report['frauds'] = report.pop('validation_frauds')
    report['accuracy'] = float(accuracy_score(labels, scores >= threshold))
    report['targets_met'] = report['accuracy'] > .8 and all(report[name] > target for name in ('precision', 'recall'))
    return report


def main():
    from lightgbm import LGBMClassifier, early_stopping, log_evaluation

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path('data/raw'))
    parser.add_argument('--output', type=Path, default=Path('artifacts/ieee_cis'))
    parser.add_argument('--iterations', type=int, default=800)
    parser.add_argument('--enhanced', action='store_true')
    parser.add_argument('--target', type=float, default=.8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / 'test.json').exists():
        raise ValueError('Ce dossier contient déjà un test final. Utiliser un autre dossier et signaler la réutilisation du test.')

    data = load_data(args.data)
    train, validation, test = chronological_split(data)
    splits = {name: {'rows': len(part), 'first_time': int(part.TransactionDT.min()),
                     'last_time': int(part.TransactionDT.max())}
              for name, part in [('train', train), ('validation', validation), ('test', test)]}
    print(json.dumps(splits), flush=True)
    x_train, x_validation = feature_frame(train, args.enhanced), feature_frame(validation, args.enhanced)
    feature_columns = list(x_train.columns)
    y_train, y_validation = train.isFraud.copy(), validation.isFraud.copy()
    categories = list(x_train.columns.intersection(list(CATEGORICAL)))
    if args.enhanced:
        categories.append('card_address')
    preprocess = ColumnTransformer([
        ('categories', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1,
                                      dtype=np.int32), categories),
    ], remainder='passthrough', verbose_feature_names_out=False).set_output(transform='pandas')
    encoded_train = preprocess.fit_transform(x_train)
    encoded_validation = preprocess.transform(x_validation)
    del data, train, validation, x_train, x_validation
    models = {
        'lightgbm': LGBMClassifier(n_estimators=args.iterations, learning_rate=.05,
                                   num_leaves=63, min_child_samples=40, reg_lambda=2,
                                   metric='average_precision', random_state=42, n_jobs=5, verbosity=-1),
    }
    reports = {}
    names = ('lightgbm', 'catboost')
    if args.enhanced:
        models = {
            name: LGBMClassifier(n_estimators=args.iterations, learning_rate=.04,
                                num_leaves=leaves, min_child_samples=20, reg_lambda=1,
                                colsample_bytree=.8, metric='average_precision',
                                random_state=42, n_jobs=5, verbosity=-1)
            for name, leaves in [('lightgbm_127', 127), ('lightgbm_63', 63)]
        }
        names = tuple(models)
    for name in names:
        if name == 'catboost':
            from catboost import CatBoostClassifier

            models[name] = CatBoostClassifier(
                iterations=min(args.iterations, 400), learning_rate=.08, depth=6,
                loss_function='Logloss', eval_metric='PRAUC', random_seed=42,
                max_ctr_complexity=1, one_hot_max_size=20,
                thread_count=5, allow_writing_files=False, verbose=50)
        model = models[name]
        print(f'Training {name}', flush=True)
        if name.startswith('lightgbm'):
            model.fit(encoded_train, y_train, categorical_feature=categories,
                      eval_set=[(encoded_validation, y_validation)], eval_metric='average_precision',
                      callbacks=[early_stopping(120, first_metric_only=True, verbose=False), log_evaluation(100)])
        else:
            model.fit(encoded_train, y_train, cat_features=categories,
                      eval_set=(encoded_validation, y_validation), early_stopping_rounds=80)
        scores = model.predict_proba(encoded_validation)[:, 1]
        decision = choose_balanced_threshold(y_validation, scores, args.target)
        reports[name] = metrics(y_validation, scores, decision['threshold'], args.target)
        print(name, json.dumps(reports[name]), flush=True)
        (args.output / 'validation.json').write_text(json.dumps(reports, indent=2))

    selected = max(reports, key=lambda name: min(reports[name]['precision'], reports[name]['recall']))
    threshold = reports[selected]['threshold']
    pipeline = Pipeline([('preprocess', preprocess), ('classifier', models[selected])])
    joblib.dump(pipeline, args.output / 'model.joblib')
    hashes = {}
    for filename in ('train_transaction.csv', 'train_identity.csv'):
        with (args.data / filename).open('rb') as stream:
            hashes[filename] = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = {'selected_model': selected, 'threshold': threshold, 'split': splits,
                'raw_feature_columns': feature_columns, 'categorical_columns': categories,
                'iterations_limit': args.iterations,
                'enhanced_features': args.enhanced, 'precision_recall_target': args.target,
                'selected_parameters': models[selected].get_params(),
                'test_status': 'reused_diagnostic' if args.enhanced else 'held_out',
                'source_sha256': hashes}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print('Selected on validation:', selected, flush=True)
    final = metrics(test.isFraud, pipeline.predict_proba(feature_frame(test, args.enhanced))[:, 1], threshold, args.target)
    final['evaluation_status'] = manifest['test_status']
    (args.output / 'test.json').write_text(json.dumps(final, indent=2))
    print('FINAL TEST', json.dumps(final), flush=True)


if __name__ == '__main__':
    main()
