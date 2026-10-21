"""Build validated interval Parquet files and auditable source/quality reports."""

import argparse
from datetime import datetime, timezone
import importlib.metadata
import logging
from pathlib import Path
import platform
import re
import shutil
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .common import read_config, sha256, write_json
from .parse import read_annual, INTERVAL_COLUMNS
from .validate import validate, to_intervals

LOGGER = logging.getLogger(__name__)


def prepare(config_path: str | Path) -> dict:
    data = read_config(config_path)['data']
    paths = [data['raw_dir'] / name for name in data['files']]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f'{path} missing. Run solarshift.data.acquire or supply the original CSV files.')
    output = data['output_dir']
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.prepare-', dir=output.parent))
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'python': platform.python_version(),
              'versions': {p: importlib.metadata.version(p) for p in ['pandas', 'numpy', 'pyarrow']},
              'config_sha256': sha256(Path(config_path)), 'source_url': data['source_url'],
              'demand_definition': 'GC only; controlled load CL remains separate; GG is gross generation.',
              'timestamp_policy': 'Australia/Sydney interval endings; DST transition channel-days excluded.',
              'target_imputation': 'none', 'files': []}
    summaries, exclusions, coverage, metadata = [], [], [], []
    try:
        for path in paths:
            LOGGER.info('Reading %s', path.name)
            match = re.search(r'(20\d{2})-(20\d{2})', path.name)
            if not match or int(match[2]) != int(match[1]) + 1:
                raise ValueError(f'Expected an original annual filename, got {path.name}')
            start, end = f'{match[1]}-07-01', f'{match[2]}-06-30'
            raw = read_annual(path)
            clean, rejected, quality = validate(raw, start, end)
            if clean.empty:
                raise ValueError(f'No accepted channel-days in {path.name}')
            metadata.append(clean[['Customer', 'Postcode', 'Generator Capacity']].drop_duplicates())
            exclusions.append(rejected)
            source_record = {'filename': path.name, 'sha256': sha256(path), 'bytes': path.stat().st_size,
                             'period_start': start, 'period_end': end, 'households': int(clean['Customer'].nunique()),
                             'channels': sorted(clean['Consumption Category'].unique().tolist()), **quality}
            source_record['accepted_intervals'] = len(clean) * 48
            report['files'].append(source_record)
            target = staging / f'intervals_{match[1]}_{match[2]}.parquet'
            writer = None
            try:
                for offset in range(0, len(clean), 3000):
                    intervals = to_intervals(clean.iloc[offset:offset + 3000])
                    table = pa.Table.from_pandas(intervals, preserve_index=False)
                    if writer is None:
                        writer = pq.ParquetWriter(target, table.schema, compression='zstd')
                    writer.write_table(table)
            finally:
                if writer:
                    writer.close()
            # Daily summaries retain gaps: no interpolation or zero filling.
            daily = clean[['Customer', 'date', 'Consumption Category']].rename(
                columns={'Customer': 'customer', 'date': 'source_date', 'Consumption Category': 'channel'}).copy()
            daily['energy_kwh'] = clean[INTERVAL_COLUMNS].sum(axis=1)
            daily['max_average_power_kw'] = clean[INTERVAL_COLUMNS].max(axis=1) / 0.5
            summaries.append(daily)
            expected = pd.MultiIndex.from_product([range(1, 301), pd.date_range(start, end), ['GC', 'GG']],
                                                  names=['customer', 'source_date', 'channel'])
            present = pd.MultiIndex.from_frame(daily[['customer', 'source_date', 'channel']])
            missing = expected.difference(present).to_frame(index=False)
            missing['source_file'] = path.name
            coverage.append(missing)
            LOGGER.info('%s: %s accepted, %s excluded channel-days', path.name, len(clean), len(rejected))
            del raw, clean, intervals, table
        combined_metadata = pd.concat(metadata).drop_duplicates()
        if combined_metadata.groupby('Customer')[['Postcode', 'Generator Capacity']].nunique().gt(1).any().any():
            raise ValueError('Household metadata changes across annual files. Resolve explicitly before combining.')
        pd.concat(summaries).to_parquet(staging / 'daily_summary.parquet', index=False)
        pd.concat(exclusions).to_csv(staging / 'excluded_channel_days.csv', index=False)
        pd.concat(coverage).to_csv(staging / 'unavailable_primary_channel_days.csv', index=False)
        combined_metadata.to_csv(staging / 'households.csv', index=False)
        report['accepted_intervals'] = sum(f['accepted_intervals'] for f in report['files'])
        report['excluded_channel_days'] = sum(f['excluded_channel_days'] for f in report['files'])
        report['unavailable_primary_channel_days'] = sum(len(c) for c in coverage)
        report['households'] = int(combined_metadata['Customer'].nunique())
        report['outputs'] = {p.name: {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in sorted(staging.iterdir())}
        write_json(staging / 'quality_report.json', report)
        output.mkdir(parents=True, exist_ok=True)
        # Computation must finish before publishing generated outputs.
        for path in staging.iterdir():
            path.replace(output / path.name)
        return report
    finally:
        shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/data.toml')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    report = prepare(args.config)
    print(f"Validated {report['accepted_intervals']:,} intervals for {report['households']} households.")
    print(f"Excluded {report['excluded_channel_days']:,} channel-days; see quality_report.json and exclusion ledger.")


if __name__ == '__main__':
    main()
