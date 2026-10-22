"""Independently match every validation forecast and target to source interval data."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    root = Path(__file__).resolve().parents[1]
    features = json.loads((root / 'data/features/manifest.json').read_text())
    result_dir = root / 'results/generated/baseline'
    summary = json.loads((result_dir / 'summary.json').read_text())
    predictions = pd.read_parquet(result_dir / 'validation_predictions.parquet')
    history = pd.concat([pd.read_parquet(root / 'data/processed' / record['filename'],
        columns=['customer', 'channel', 'source_date', 'slot', 'energy_kwh'],
        filters=[('customer', 'in', features['cohort']), ('channel', 'in', ['GC', 'GG']),
                 ('source_date', '<=', pd.Timestamp(features['splits']['validation_end']))])
        for record in features['source_files']])
    keys = ['customer', 'channel', 'source_date', 'slot']
    lookup = history.set_index(keys).energy_kwh
    target_keys = pd.MultiIndex.from_frame(predictions[keys])
    previous = predictions[keys].copy()
    previous['source_date'] -= pd.Timedelta(days=7)
    np.testing.assert_array_equal(lookup.reindex(target_keys).to_numpy(), predictions.actual_kwh)
    np.testing.assert_array_equal(lookup.reindex(pd.MultiIndex.from_frame(previous)).to_numpy(), predictions.predicted_kwh)
    assert not predictions.source_date.ge(features['splits']['test_start']).any()
    checked_features = 0
    for record in features['files']:
        frame = pd.read_parquet(root / 'data/features' / record['filename'])
        for column in features['availability_columns']:
            assert frame[column].notna().all() and (frame[column] <= frame.issued_at).all()
        assert set(frame.split) <= {'train', 'validation'}
        checked_features += len(frame)
    checks = []
    for metric in summary['metrics']:
        if metric['scope'] != 'household_interval_weighted':
            continue
        frame = predictions[predictions.channel == metric['channel']]
        if metric['window'] == 'evening_16_21':
            frame = frame[frame.slot.between(33, 42)]
        difference = frame.predicted_kwh.to_numpy() - frame.actual_kwh.to_numpy()
        mae = float(np.abs(difference).sum() / len(difference))
        rmse = float(np.sqrt(np.dot(difference, difference) / len(difference)))
        assert math.isclose(mae, metric['mae_kwh'], abs_tol=1e-12)
        assert math.isclose(rmse, metric['rmse_kwh'], abs_tol=1e-12)
        checks.append({'channel': metric['channel'], 'window': metric['window'], 'mae_kwh': mae, 'rmse_kwh': rmse})
    evidence = {'status': 'passed', 'predictions_matched_to_original_interval_history': len(predictions),
                'feature_rows_with_cutoff_provenance_checked': checked_features,
                'final_test_predictions': 0, 'independent_metric_checks': checks}
    target = root / 'results/evidence/baseline_audit.json'
    target.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
