"""Independent NumPy/source/bare-Booster audit of the default modelling experiment."""

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'results/generated/xgboost'
    summary = json.loads((output / 'summary.json').read_text())
    training = json.loads((output / 'training_summary.json').read_text())
    manifest_path = root / 'data/features/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert digest(manifest_path) == training['feature_manifest_sha256'] == summary['feature_manifest_sha256']
    assert digest(output / 'training_summary.json') == summary['training_summary_sha256']
    assert digest(output / 'validation_predictions.parquet') == summary['predictions_sha256']
    predictions = pd.read_parquet(output / 'validation_predictions.parquet')
    keys = ['customer', 'channel', 'source_date', 'slot']
    assert not predictions.duplicated(keys).any()
    assert predictions.source_date.between(manifest['splits']['validation_start'], manifest['splits']['validation_end']).all()
    baseline = pd.read_parquet(root / 'results/generated/baseline/validation_predictions.parquet').set_index(keys).sort_index()
    indexed = predictions.set_index(keys).sort_index()
    pd.testing.assert_index_equal(indexed.index, baseline.index)
    np.testing.assert_array_equal(indexed.actual_kwh, baseline.actual_kwh)
    np.testing.assert_array_equal(indexed.baseline_kwh, baseline.predicted_kwh)
    # Join directly to development source intervals; no test source is read.
    source_parts = []
    for record in manifest['source_files']:
        assert '2012_2013' not in record['filename']
        path = root / 'data/processed' / record['filename']
        assert digest(path) == record['sha256']
        source_parts.append(pd.read_parquet(path, columns=keys + ['energy_kwh'],
            filters=[('customer', 'in', manifest['cohort']), ('channel', 'in', ['GC', 'GG']),
                     ('source_date', '<=', pd.Timestamp(manifest['splits']['validation_end']))]))
    source = pd.concat(source_parts).set_index(keys).energy_kwh
    np.testing.assert_array_equal(source.reindex(indexed.index), indexed.actual_kwh)
    lag_keys = predictions[keys].copy()
    lag_keys['source_date'] -= pd.Timedelta(days=7)
    np.testing.assert_array_equal(source.reindex(pd.MultiIndex.from_frame(lag_keys)), predictions.baseline_kwh)
    refits = []
    for channel in ['GC', 'GG']:
        parts = []
        for record in manifest['files']:
            if record['channel'] != channel:
                continue
            path = root / 'data/features' / record['filename']
            assert digest(path) == record['sha256']
            frame = pd.read_parquet(path)
            assert set(frame.split) == {'train', 'validation'}
            for column in manifest['availability_columns']:
                assert frame[column].notna().all() and (frame[column] <= frame.issued_at).all()
            parts.append(frame)
        frame = pd.concat(parts).sort_values(keys)
        valid = frame[frame.split == 'validation']
        train = frame[frame.split == 'train']
        assert train.source_date.max() < valid.source_date.min()
        metadata = json.loads((output / channel / 'metadata.json').read_text())
        assert metadata == training['selected'][channel]
        assert digest(output / channel / 'model.ubj') == metadata['model_sha256']
        booster = xgb.Booster()
        booster.load_model(output / channel / 'model.ubj')
        matrix = xgb.DMatrix(valid[manifest['feature_columns']].astype('float32'))
        reloaded = np.maximum(booster.predict(matrix), 0).astype(float)
        expected = predictions[predictions.channel.eq(channel)].sort_values(keys)
        np.testing.assert_array_equal(reloaded, expected.predicted_kwh)
        # Independently repeat the winning fit from recorded parameters and seed.
        params = {k: v for k, v in metadata['selected']['parameters'].items() if k != 'name'}
        model = xgb.XGBRegressor(**params, objective='reg:squarederror', tree_method='hist',
            device='cpu', random_state=metadata['seed'], n_jobs=metadata['threads'])
        model.fit(train[manifest['feature_columns']].astype('float32'), train.energy_kwh)
        repeat = np.maximum(model.predict(valid[manifest['feature_columns']].astype('float32')), 0).astype(float)
        np.testing.assert_array_equal(repeat, reloaded)
        candidate_scores = [r['selection_mae_kwh'] for r in training['candidates'] if r['channel'] == channel]
        assert metadata['selected']['selection_mae_kwh'] == min(candidate_scores)
        refits.append({'channel': channel, 'training_rows': len(train), 'validation_rows': len(valid),
                       'repeat_fit_exact_prediction_match': True, 'bare_booster_reload_exact_match': True})
    checks = []
    for record in summary['metrics']:
        frame = predictions[predictions.channel.eq(record['channel'])].copy()
        field = 'baseline_kwh' if record['model'] == 'weekly_persistence' else 'predicted_kwh'
        if record['scope'] == 'complete_cohort_sum':
            complete_dates = frame.groupby('source_date').apply(
                lambda f: len(f) == 48 * len(manifest['cohort']) and set(f.customer) == set(manifest['cohort']) and
                f.groupby('customer').slot.apply(lambda s: set(s) == set(range(1, 49))).all(), include_groups=False)
            frame = frame[frame.source_date.isin(complete_dates[complete_dates].index)]
            frame = frame.groupby(['source_date', 'slot'], as_index=False)[['actual_kwh', field]].sum()
        if record['window'] == 'evening_16_21':
            frame = frame[frame.slot.between(33, 42)]
        delta = frame[field].to_numpy() - frame.actual_kwh.to_numpy()
        mae, rmse = float(np.abs(delta).sum() / len(delta)), float(np.sqrt(np.dot(delta, delta) / len(delta)))
        assert len(delta) == record['n']
        assert math.isclose(mae, record['mae_kwh'], abs_tol=1e-12)
        assert math.isclose(rmse, record['rmse_kwh'], abs_tol=1e-12)
        checks.append({k: record[k] for k in ['model', 'scope', 'channel', 'window', 'n', 'mae_kwh', 'rmse_kwh']})
    # Independently check all saved household scores, not just pooled values.
    household_scores = pd.read_csv(output / 'household_metrics.csv')
    for record in household_scores.to_dict('records'):
        frame = predictions[predictions.customer.eq(record['customer']) & predictions.channel.eq(record['channel'])]
        if record['window'] == 'evening_16_21':
            frame = frame[frame.slot.between(33, 42)]
        field = 'baseline_kwh' if record['model'] == 'weekly_persistence' else 'predicted_kwh'
        delta = frame[field] - frame.actual_kwh
        assert math.isclose(float(delta.abs().mean()), record['mae_kwh'], abs_tol=1e-12)
        assert math.isclose(float(np.sqrt((delta ** 2).mean())), record['rmse_kwh'], abs_tol=1e-12)
    evidence = {'status': 'passed', 'validation_rows_matched_to_sources_and_baseline': len(predictions),
                'test_predictions': 0, 'refits': refits, 'independent_metric_checks': checks,
                'household_metric_rows_checked': len(household_scores),
                'note': 'Audit refits are outside the recorded search carbon estimate.'}
    (root / 'results/evidence/model_audit.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
