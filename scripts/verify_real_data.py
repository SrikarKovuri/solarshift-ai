"""Independent source-to-output energy audit; requires the real prepared dataset."""

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from solarshift.data.common import read_config, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/data.toml')
    args = parser.parse_args()
    config = read_config(args.config)['data']
    quality = json.loads((config['output_dir'] / 'quality_report.json').read_text())
    excluded = set()
    with (config['output_dir'] / 'excluded_channel_days.csv').open() as stream:
        for row in csv.DictReader(stream):
            excluded.add((row['source_file'], int(row['source_line'])))
    results = []
    for source in quality['files']:
        totals = {'GC': 0.0, 'GG': 0.0, 'CL': 0.0}
        accepted_days = 0
        with (config['raw_dir'] / source['filename']).open() as stream:
            reader = csv.reader(stream)
            next(reader)
            next(reader)
            for line, row in enumerate(reader, 3):
                if (source['filename'], line) in excluded:
                    continue
                energies = [float(value) for value in row[5:53]]
                assert len(energies) == 48 and all(math.isfinite(v) and v >= 0 for v in energies)
                assert len(row) == 53 or not row[53].strip(), 'Non-actual row leaked into accepted set'
                totals[row[3]] += math.fsum(energies)
                accepted_days += 1
        years = source['filename'].split()[-1].removesuffix('.csv').replace('-', '_')
        parquet = pq.ParquetFile(config['output_dir'] / f'intervals_{years}.parquet')
        observed = {'GC': 0.0, 'GG': 0.0, 'CL': 0.0}
        count = 0
        for batch in parquet.iter_batches(batch_size=200000, columns=['channel', 'energy_kwh', 'average_power_kw', 'slot']):
            frame = batch.to_pandas()
            assert np.isfinite(frame.energy_kwh).all() and (frame.energy_kwh >= 0).all()
            assert np.array_equal(frame.average_power_kw.to_numpy(), frame.energy_kwh.to_numpy() * 2)
            assert frame.slot.between(1, 48).all()
            for channel, value in frame.groupby('channel').energy_kwh.sum().items():
                observed[channel] += float(value)
            count += len(frame)
        assert count == accepted_days * 48 == source['accepted_intervals']
        for channel in totals:
            assert math.isclose(totals[channel], observed[channel], rel_tol=1e-10, abs_tol=1e-6)
        results.append({'file': source['filename'], 'accepted_intervals': count,
                        'source_energy_kwh': totals, 'parquet_energy_kwh': observed,
                        'source_to_parquet_totals': 'passed', 'power_and_slot_invariants': 'passed'})
    write_json(Path('results/evidence/real_data_audit.json'), {'checks': results, 'status': 'passed'})
    print(f"Source-to-Parquet energy totals and physical invariants passed for {sum(r['accepted_intervals'] for r in results):,} readings.")


if __name__ == '__main__':
    main()
