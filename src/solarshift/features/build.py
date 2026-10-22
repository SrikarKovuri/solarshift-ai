"""Create a reproducible development cohort and forecast-ready dataset."""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import tempfile
import tomllib

import numpy as np
import pandas as pd

from solarshift.data.common import sha256, write_json
from .dataset import build_channel, FEATURE_COLUMNS, AVAILABILITY_COLUMNS, assign_split


def read_config(path):
    path = Path(path).resolve()
    config = tomllib.loads(path.read_text())['forecast']
    for name in ['processed_dir', 'output_dir', 'results_dir']:
        config[name] = path.parent.parent / config[name]
    assign_split(pd.Series([], dtype='datetime64[ns]'), config)
    if config['timezone'] != 'Australia/Sydney' or not 0 <= config['issue_hour'] <= 23:
        raise ValueError('Invalid forecast clock configuration')
    if config['observation_delay_minutes'] < 0 or config['cohort_size'] < 1:
        raise ValueError('Invalid delay or cohort size')
    if not 0 < config['minimum_training_coverage'] <= 1:
        raise ValueError('Training coverage must be in (0, 1]')
    return config


def select_cohort(daily, config):
    train = daily[daily.source_date.between(config['train_start'], config['train_end']) & daily.channel.isin(['GC', 'GG'])]
    if train.duplicated(['customer', 'source_date', 'channel']).any():
        raise ValueError('Duplicate training coverage rows')
    expected = len(pd.date_range(config['train_start'], config['train_end']))
    counts = train.groupby(['customer', 'channel']).size().unstack(fill_value=0).reindex(columns=['GC', 'GG'], fill_value=0)
    eligible = counts.index[(counts / expected).min(axis=1) >= config['minimum_training_coverage']].to_numpy()
    if len(eligible) < config['cohort_size']:
        raise ValueError('Insufficient training-eligible households for configured cohort')
    selected = sorted(np.random.default_rng(config['cohort_seed']).choice(sorted(eligible), config['cohort_size'], replace=False).tolist())
    return selected, {'eligible_households': len(eligible), 'training_calendar_days': expected,
                      'coverage_threshold': config['minimum_training_coverage'], 'seed': config['cohort_seed'],
                      'selection': 'Seeded uniform sample of training-eligible households; not a representative population sample.'}


def build(path):
    config = read_config(path)
    root = config['processed_dir']
    quality = json.loads((root / 'quality_report.json').read_text())
    if sha256(root / 'daily_summary.parquet') != quality['outputs']['daily_summary.parquet']['sha256']:
        raise ValueError('Training coverage source changed since data validation')
    daily = pd.read_parquet(root / 'daily_summary.parquet', filters=[('source_date', '>=', pd.Timestamp(config['train_start'])),
                          ('source_date', '<=', pd.Timestamp(config['train_end']))])
    cohort, selection = select_cohort(daily, config)
    output = config['output_dir']; output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.features-', dir=output.parent))
    manifest = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'config_sha256': sha256(Path(path)),
                'data_quality_manifest_sha256': sha256(root / 'quality_report.json'), 'cohort': cohort,
                'coverage_source_sha256': quality['outputs']['daily_summary.parquet']['sha256'],
                'selection': selection, 'feature_columns': FEATURE_COLUMNS, 'availability_columns': AVAILABILITY_COLUMNS,
                'issue_hour_local': config['issue_hour'], 'observation_delay_minutes': config['observation_delay_minutes'],
                'splits': {k: v for k, v in config.items() if k.endswith('_start') or k.endswith('_end')},
                'final_test': 'Reserved; observations on/after test_start are not loaded by this command.',
                'files': [], 'source_files': []}
    # Exclude entire annual sources outside development before any parquet reads.
    sources = []
    for record in quality['files']:
        if pd.Timestamp(record['period_start']) > pd.Timestamp(config['validation_end']):
            continue
        years = record['filename'].split()[-1].removesuffix('.csv').replace('-', '_')
        filename = f'intervals_{years}.parquet'
        if sha256(root / filename) != quality['outputs'][filename]['sha256']:
            raise ValueError(f'Processed source changed since validation: {filename}')
        sources.append(root / filename)
        manifest['source_files'].append({'filename': filename, 'sha256': quality['outputs'][filename]['sha256']})
    rejected = []
    columns = ['customer', 'channel', 'source_date', 'slot', 'capacity_kwp', 'interval_start', 'interval_end', 'energy_kwh']
    try:
        for customer in cohort:
            history = pd.concat([pd.read_parquet(source, columns=columns, filters=[('customer', '==', customer),
                ('channel', 'in', ['GC', 'GG']), ('source_date', '<=', pd.Timestamp(config['validation_end']))]) for source in sources])
            for channel in ['GC', 'GG']:
                frame, excluded = build_channel(history[history.channel == channel], config)
                rejected.append(excluded)
                filename = f'household_{customer}_{channel}.parquet'
                frame.to_parquet(staging / filename, index=False)
                counts = frame.groupby('split').size().to_dict()
                if not {'train', 'validation'} <= set(counts):
                    raise ValueError(f'No usable training/validation data for {customer}/{channel}')
                manifest['files'].append({'filename': filename, 'customer': customer, 'channel': channel,
                                          'rows_by_split': {k: int(v) for k, v in counts.items()},
                                          'sha256': sha256(staging / filename)})
            logging.info('Prepared household %s', customer)
        pd.concat(rejected).to_csv(staging / 'excluded_forecast_days.csv', index=False)
        manifest['excluded_observed_channel_days'] = sum(len(f) for f in rejected)
        write_json(staging / 'manifest.json', manifest)
        output.mkdir(parents=True, exist_ok=True)
        for file in staging.iterdir():
            file.replace(output / file.name)
    finally:
        shutil.rmtree(staging)
    print(f'Prepared {len(cohort)} households, {len(manifest["files"])} target datasets; final test untouched.')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/forecast.toml')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    build(args.config)


if __name__ == '__main__':
    main()
