import csv
from pathlib import Path

import pytest

from solarshift.data.parse import INTERVAL_COLUMNS, METADATA, read_annual


@pytest.fixture
def write_csv(tmp_path):
    def write(rows=None, quality=True, notice=True, filename='Solar home 2010-2011.csv'):
        target = tmp_path / filename
        if rows is None:
            rows = [[1, 3.78, 2076, channel, '1-Jul-10'] + [0.5] * 48 + ([''] if quality else [])
                    for channel in ['GC', 'GG']]
        with target.open('w', newline='') as stream:
            writer = csv.writer(stream)
            if notice:
                writer.writerow(['Synthetic test fixture; never use for experimental metrics'])
            writer.writerow(METADATA + INTERVAL_COLUMNS + (['Row Quality'] if quality else []))
            writer.writerows(rows)
        return target
    return write


@pytest.fixture
def valid_frame(write_csv):
    return read_annual(write_csv())
