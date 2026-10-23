"""Hash-checked development datasets and reloadable, target-specific XGBoost models."""

import json
from pathlib import Path
import tomllib

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from solarshift.data.common import sha256
from solarshift.features.build import read_config as read_forecast_config
from solarshift.features.dataset import FEATURE_COLUMNS, assert_available, assign_split

KEYS = ['customer', 'channel', 'source_date', 'slot']


def read_config(path):
    path = Path(path).resolve()
    config = tomllib.loads(path.read_text())
    for key in ['forecast_config', 'output_dir']:
        config['experiment'][key] = path.parent.parent / config['experiment'][key]
    experiment = config['experiment']
    if experiment['threads'] < 1 or experiment['threads'] > 16:
        raise ValueError('Use 1–16 CPU threads')
    for key in ['selection_demand', 'selection_pv']:
        if experiment[key] not in ['full_day', 'evening_16_21']:
            raise ValueError('Unknown validation selection window')
    names = [c['name'] for c in config['candidates']]
    if not names or len(names) != len(set(names)):
        raise ValueError('Candidate names must be unique and nonempty')
    for candidate in config['candidates']:
        if not 1 <= candidate['n_estimators'] <= 1000 or not 1 <= candidate['max_depth'] <= 10:
            raise ValueError('Candidate exceeds bounded CPU search limits')
    return config


def load_development(forecast_path):
    config = read_forecast_config(forecast_path)
    root = config['output_dir']
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['config_sha256'] != sha256(Path(forecast_path)):
        raise ValueError('Forecast configuration changed; rebuild features')
    if manifest['feature_columns'] != FEATURE_COLUMNS:
        raise ValueError('Feature schema mismatch')
    cohort = manifest['cohort']
    expected = {(c, ch) for c in cohort for ch in ['GC', 'GG']}
    records = [(r['customer'], r['channel']) for r in manifest['files']]
    if len(cohort) != len(set(cohort)) or set(records) != expected or len(records) != len(expected):
        raise ValueError('Feature manifest must contain the complete unique cohort and both targets')
    parts = []
    for record in manifest['files']:
        filename = record['filename']
        if Path(filename).name != filename or sha256(root / filename) != record['sha256']:
            raise ValueError('Feature file hash/path mismatch')
        frame = pd.read_parquet(root / filename)
        if frame.empty or set(frame.split) != {'train', 'validation'}:
            raise ValueError('Only nonempty training and validation partitions are permitted')
        if not frame.customer.eq(record['customer']).all() or not frame.channel.eq(record['channel']).all():
            raise ValueError('Feature target/cohort identity mismatch')
        if not frame.split.eq(assign_split(frame.source_date, config)).all():
            raise ValueError('Feature dates do not match chronological partitions')
        if frame.duplicated(KEYS).any():
            raise ValueError('Duplicate forecast keys')
        days = frame.groupby(['customer', 'channel', 'source_date']).slot
        if not days.apply(lambda s: sorted(s) == list(range(1, 49))).all():
            raise ValueError('Forecasts require all 48 distinct slots')
        assert_available(frame)
        feature_matrix(frame)
        if not np.isfinite(frame.energy_kwh).all() or (frame.energy_kwh < 0).any():
            raise ValueError('Invalid target values')
        parts.append(frame)
    return pd.concat(parts, ignore_index=True).sort_values(KEYS).reset_index(drop=True), manifest, config


def feature_matrix(frame):
    """Explicit allowlist: target values, identity and provenance never enter X."""
    selected = frame.loc[:, FEATURE_COLUMNS].astype('float32')
    if selected.empty or not np.isfinite(selected.to_numpy()).all():
        raise ValueError('Model features must be nonempty and finite')
    return selected


def make_model(candidate, seed, threads):
    parameters = {k: v for k, v in candidate.items() if k != 'name'}
    return XGBRegressor(**parameters, objective='reg:squarederror', tree_method='hist',
                        device='cpu', random_state=seed, n_jobs=threads)


def predict_nonnegative(model, frame):
    raw = model.predict(feature_matrix(frame))
    if not np.isfinite(raw).all():
        raise ValueError('Model produced non-finite predictions')
    # Declared physical bound, applied identically during selection and inference.
    # No capacity cap or night-time zero override is fitted to validation actuals.
    return np.maximum(raw, 0).astype(float)


def load_model(directory, channel):
    directory = Path(directory)
    metadata = json.loads((directory / 'metadata.json').read_text())
    if channel not in ['GC', 'GG'] or metadata['channel'] != channel:
        raise ValueError('Wrong model target')
    if metadata['feature_columns'] != FEATURE_COLUMNS or metadata['prediction_policy'] != 'clip_lower_zero':
        raise ValueError('Incompatible model feature/prediction policy')
    path = directory / 'model.ubj'
    if sha256(path) != metadata['model_sha256']:
        raise ValueError('Model hash mismatch')
    model = XGBRegressor()
    model.load_model(path)
    model.set_params(n_jobs=metadata['threads'])
    if model.get_booster().feature_names != FEATURE_COLUMNS:
        raise ValueError('Stored model feature order mismatch')
    return model, metadata


def select_day(frame, customer, day):
    selected = frame[frame.customer.eq(customer) & frame.source_date.eq(pd.Timestamp(day))].copy()
    if set(selected.channel) != {'GC', 'GG'} or set(selected.split) != {'validation'}:
        raise ValueError('Choose a cohort household and an eligible validation date for both targets')
    for _, group in selected.groupby('channel'):
        if sorted(group.slot) != list(range(1, 49)):
            raise ValueError('Selected day must contain 48 distinct slots per target')
    return selected.sort_values(['channel', 'slot'])
