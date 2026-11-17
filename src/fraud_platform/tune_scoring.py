"""Compare des modèles servis par l'API et choisit le seuil sur la validation."""

import argparse
import json
from pathlib import Path

import duckdb
import joblib
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OrdinalEncoder

from fraud_platform.baseline import evaluate_scores
from fraud_platform.features import FEATURE_COLUMNS, enrich_scoring_features
from fraud_platform.threshold import choose_balanced_threshold
from fraud_platform.threshold import summarize_decisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/modeling/transactions.parquet'))
    parser.add_argument('--output', type=Path, default=Path('artifacts/scoring_balanced'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(config={'threads': 4}) as db:
        data = db.read_parquet(str(args.source)).df()
    train = data[data['split'] == 'train']
    validation = data[data['split'] == 'validation']
    test = data[data['split'] == 'test']
    columns = list(FEATURE_COLUMNS)
    categories = ['transaction_type', 'hour_of_day']
    old_model = joblib.load('artifacts/lightgbm/lightgbm.joblib')
    candidates = [('existing', old_model)]
    for weight, leaves in [(1, 31), (20, 31), (1, 63)]:
        preprocess = ColumnTransformer([
            ('categories', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1,
                                          dtype=np.int32), categories),
        ], remainder='passthrough', verbose_feature_names_out=False).set_output(transform='pandas')
        classifier = LGBMClassifier(n_estimators=350, learning_rate=0.05, num_leaves=leaves,
                                    scale_pos_weight=weight, min_child_samples=40,
                                    random_state=42, n_jobs=5, verbosity=-1)
        model = Pipeline([('features', FunctionTransformer(enrich_scoring_features)),
                          ('preprocess', preprocess), ('classifier', classifier)])
        name = f'weight_{weight}_leaves_{leaves}'
        print(f'Training {name}', flush=True)
        model.fit(train[columns], train['is_fraud'], classifier__categorical_feature=categories)
        candidates.append((name, model))

    reports = {}
    for name, model in candidates:
        scores = model.predict_proba(validation[columns])[:, 1]
        decision = choose_balanced_threshold(validation['is_fraud'], scores)
        reports[name] = {**evaluate_scores(validation['is_fraud'], scores, decision['threshold']), **decision}
        print(name, json.dumps(reports[name]), flush=True)
    winner = max(reports, key=lambda name: min(reports[name]['precision'], reports[name]['recall']))
    model = dict(candidates)[winner]
    threshold = reports[winner]['threshold']
    diagnostic = evaluate_scores(test['is_fraud'], model.predict_proba(test[columns])[:, 1], threshold)
    diagnostic.update(summarize_decisions(test['is_fraud'], model.predict_proba(test[columns])[:, 1], threshold, 20))
    diagnostic['accuracy'] = 1 - diagnostic['error_rate']
    report = {'selected': winner, 'selection_split': 'validation', 'candidates': reports,
              'reused_test_diagnostic': diagnostic,
              'test_note': 'Previously consulted test split; independent confirmation required.'}
    joblib.dump(model, args.output / 'lightgbm.joblib')
    (args.output / 'threshold_margin.json').write_text(json.dumps({
        'validation': reports[winner], 'reused_test_diagnostic': diagnostic}, indent=2))
    validation_report = {**reports[winner], 'model': winner, 'features': columns,
                         'train_rows': len(train), 'train_frauds': int(train['is_fraud'].sum())}
    (args.output / 'validation.json').write_text(json.dumps(validation_report, indent=2))
    (args.output / 'comparison.json').write_text(json.dumps(report, indent=2))
    print('SELECTED', winner, 'DIAGNOSTIC', json.dumps(diagnostic), flush=True)


if __name__ == '__main__':
    main()
