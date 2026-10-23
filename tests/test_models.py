"""Small synthetic fixtures verify behaviour; they are never experimental evidence."""

from contextlib import contextmanager
import json

import numpy as np
import pandas as pd
import pytest

from solarshift.data.common import sha256, write_json
from solarshift.features.dataset import build_channel, FEATURE_COLUMNS, AVAILABILITY_COLUMNS
from solarshift.models.boosted import (feature_matrix, make_model, predict_nonnegative,
                                      load_model, load_development, select_day)
from solarshift.models.train import train
from solarshift.models.forecast import forecast_day
from solarshift.evaluation.boosted import improvement, check_baseline
from solarshift.evaluation.baseline import evaluate


@pytest.fixture
def experiment(tmp_path):
    (tmp_path / 'configs').mkdir()
    (tmp_path / 'features').mkdir()
    forecast = tmp_path / 'configs/forecast.toml'
    forecast.write_text('''[forecast]
processed_dir = "processed"
output_dir = "features"
results_dir = "baseline"
timezone = "Australia/Sydney"
issue_hour = 18
observation_delay_minutes = 30
cohort_size = 1
cohort_seed = 2112
minimum_training_coverage = 0.95
train_start = "2011-11-01"
train_end = "2011-12-31"
validation_start = "2012-01-01"
validation_end = "2012-01-10"
test_start = "2012-01-11"
test_end = "2012-02-01"
''')
    from solarshift.features.build import read_config
    config = read_config(forecast)
    records = []
    for channel in ['GC', 'GG']:
        days = pd.date_range('2011-11-01', '2012-01-10')
        dates = pd.Series(np.repeat(days, 48))
        slots = np.tile(np.arange(1, 49), len(days))
        endings = (dates + pd.to_timedelta(slots * 30, unit='m')).dt.tz_localize('Australia/Sydney')
        frame = pd.DataFrame({'customer': 1, 'channel': channel, 'source_date': dates,
            'slot': slots, 'capacity_kwp': 3.0, 'interval_start': endings - pd.Timedelta(minutes=30),
            'interval_end': endings, 'energy_kwh': np.maximum(0, np.sin(slots / 48 * 2 * np.pi)) + 0.1})
        built, _ = build_channel(frame, config)
        filename = f'household_1_{channel}.parquet'
        built.to_parquet(tmp_path / 'features' / filename, index=False)
        records.append({'filename': filename, 'customer': 1, 'channel': channel,
                        'sha256': sha256(tmp_path / 'features' / filename)})
    write_json(tmp_path / 'features/manifest.json', {'config_sha256': sha256(forecast),
               'feature_columns': FEATURE_COLUMNS, 'availability_columns': AVAILABILITY_COLUMNS,
               'cohort': [1], 'files': records})
    models = tmp_path / 'configs/models.toml'
    models.write_text('''[experiment]
forecast_config = "configs/forecast.toml"
output_dir = "models"
seed = 2112
threads = 1
selection_demand = "evening_16_21"
selection_pv = "full_day"
[carbon]
country_iso_code = "AUS"
cpu_power_w = 15.0
ram_power_w = 3.0
[[candidates]]
name = "small"
n_estimators = 4
max_depth = 2
learning_rate = 0.2
[[candidates]]
name = "larger"
n_estimators = 8
max_depth = 3
learning_rate = 0.2
''')
    return tmp_path, forecast, models


def test_feature_allowlist_ignores_targets_and_column_order(experiment):
    _, path, _ = experiment
    frame, _, _ = load_development(path)
    original = feature_matrix(frame)
    frame['energy_kwh'] = 1e9
    frame['customer'] = 9999
    pd.testing.assert_frame_equal(original, feature_matrix(frame[frame.columns[::-1]]))
    assert 'energy_kwh' not in original.columns
    frame.loc[frame.index[0], 'lag_2d_kwh'] = np.nan
    with pytest.raises(ValueError, match='finite'):
        feature_matrix(frame)


def test_deterministic_fitting_and_physical_bound(experiment):
    _, path, _ = experiment
    frame, _, _ = load_development(path)
    candidate = {'n_estimators': 5, 'max_depth': 2, 'subsample': 0.8}
    a, b = make_model(candidate, 2112, 1), make_model(candidate, 2112, 1)
    a.fit(feature_matrix(frame), frame.energy_kwh)
    b.fit(feature_matrix(frame), frame.energy_kwh)
    np.testing.assert_array_equal(predict_nonnegative(a, frame), predict_nonnegative(b, frame))
    class NegativeModel:
        def predict(self, features):
            return np.full(len(features), -2.0)
    np.testing.assert_array_equal(predict_nonnegative(NegativeModel(), frame), np.zeros(len(frame)))


@pytest.mark.parametrize('change', ['hash', 'test_date', 'target', 'duplicate', 'missing_slot', 'leakage', 'missing_target'])
def test_development_loader_rejects_invalid_inputs(experiment, change):
    root, path, _ = experiment
    manifest_path = root / 'features/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    file = root / 'features' / manifest['files'][0]['filename']
    frame = pd.read_parquet(file)
    if change == 'hash':
        frame.loc[0, 'energy_kwh'] += 1
    elif change == 'test_date':
        frame.loc[0, 'source_date'] = pd.Timestamp('2012-01-11')
    elif change == 'target':
        frame.loc[0, 'channel'] = 'GG'
    elif change == 'duplicate':
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    elif change == 'missing_slot':
        frame = frame.iloc[1:]
    elif change == 'leakage':
        frame.loc[0, 'lag_2d_available_at'] = frame.loc[0, 'issued_at'] + pd.Timedelta(minutes=1)
    elif change == 'missing_target':
        manifest['files'] = manifest['files'][:1]
    frame.to_parquet(file, index=False)
    if change != 'hash':
        manifest['files'][0]['sha256'] = sha256(file)
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError):
        load_development(path)


@pytest.mark.parametrize('customer,day', [(999, '2012-01-01'), (1, '2011-12-20'), (1, '2012-01-11')])
def test_day_forecast_rejects_nonvalidation_or_unsupported_selection(experiment, customer, day):
    _, path, _ = experiment
    frame, _, _ = load_development(path)
    with pytest.raises(ValueError, match='validation'):
        select_day(frame, customer, day)


def test_baseline_mask_actual_and_value_identity():
    frame = pd.DataFrame({'customer': [1], 'channel': ['GC'], 'source_date': pd.to_datetime(['2012-01-01']),
                          'slot': [1], 'actual_kwh': [1.0], 'baseline_kwh': [0.5]})
    baseline = frame.rename(columns={'baseline_kwh': 'predicted_kwh'})
    summary = {'feature_manifest_sha256': 'abc'}
    check_baseline(frame, baseline, 'abc', summary)
    for field, value in [('slot', 2), ('actual_kwh', 2), ('predicted_kwh', 2)]:
        altered = baseline.copy(); altered[field] = value
        with pytest.raises(ValueError):
            check_baseline(frame, altered, 'abc', summary)
    with pytest.raises(ValueError):
        check_baseline(frame, baseline, 'changed', summary)


def test_improvement_handles_worse_models_and_zero_baseline():
    assert improvement(2, 1) == 50
    assert improvement(1, 2) == -100
    assert improvement(0, 0.1) is None


@pytest.mark.parametrize('failure', ['initialisation', 'missing_estimate'])
def test_carbon_unavailable_does_not_claim_zero_or_block_training(tmp_path, monkeypatch, failure):
    from solarshift.models.tracking import training_carbon
    class UnavailableTracker:
        def __init__(self, **kwargs):
            assert kwargs['save_to_api'] is False
            if failure == 'initialisation':
                raise RuntimeError('Hardware unavailable in synthetic test')
        def start(self):
            pass
        def stop(self):
            return None
    monkeypatch.setattr('codecarbon.OfflineEmissionsTracker', UnavailableTracker)
    with training_carbon(tmp_path, {'country_iso_code': 'AUS', 'cpu_power_w': 15, 'ram_power_w': 3}):
        (tmp_path / 'training_proceeded').touch()
    result = json.loads((tmp_path / 'carbon.json').read_text())
    assert result['status'] == 'unavailable'
    assert 'error' in result and 'emissions' not in result
    assert (tmp_path / 'training_proceeded').exists()


def test_training_reload_evaluation_forecast_end_to_end(experiment, monkeypatch):
    root, forecast, models = experiment
    @contextmanager
    def no_tracker(output, config):
        # Avoid hardware sampling in synthetic unit tests; explicitly unavailable.
        evidence = {'status': 'unavailable'}
        yield evidence
        write_json(output / 'carbon.json', evidence)
    monkeypatch.setattr('solarshift.models.train.training_carbon', no_tracker)
    evaluate(forecast)
    summary = train(models)
    assert summary['test_evaluated'] is False
    assert summary['predictions'] == 10 * 48 * 2
    prediction = forecast_day(models, 1, '2012-01-02')
    assert len(prediction) == 96
    assert prediction.groupby('channel').size().eq(48).all()
    all_predictions = pd.read_parquet(root / 'models/validation_predictions.parquet')
    sample = all_predictions[all_predictions.source_date.eq('2012-01-02')].sort_values(['channel', 'slot'])
    np.testing.assert_array_equal(prediction.predicted_kwh, sample.predicted_kwh)
    training = json.loads((root / 'models/training_summary.json').read_text())
    for channel in ['GC', 'GG']:
        scores = [r['selection_mae_kwh'] for r in training['candidates'] if r['channel'] == channel]
        assert training['selected'][channel]['selected']['selection_mae_kwh'] == min(scores)
    with pytest.raises(ValueError, match='target'):
        load_model(root / 'models/GC', 'GG')
    metadata = root / 'models/GC/metadata.json'
    original = json.loads(metadata.read_text())
    altered = {**original, 'feature_columns': FEATURE_COLUMNS[::-1]}
    write_json(metadata, altered)
    with pytest.raises(ValueError, match='feature'):
        load_model(metadata.parent, 'GC')
    write_json(metadata, original)
    with (root / 'models/GC/model.ubj').open('ab') as stream:
        stream.write(b'corrupt')
    with pytest.raises(ValueError, match='hash'):
        load_model(metadata.parent, 'GC')
