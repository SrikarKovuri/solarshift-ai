"""Read the inspected Ausgrid annual wide-row format without hiding invalid values."""

from pathlib import Path
import csv
import numpy as np
import pandas as pd

INTERVAL_COLUMNS = [f'{n // 2}:{(n % 2) * 30:02d}' for n in range(1, 48)] + ['0:00']
METADATA = ['Customer', 'Generator Capacity', 'Postcode', 'Consumption Category', 'date']


def read_annual(path: Path) -> pd.DataFrame:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        first = next(csv.reader(stream))
    skip = 0 if first[:5] == METADATA else 1
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        if skip:
            next(reader)
        header = next(reader)
    if header not in [METADATA + INTERVAL_COLUMNS, METADATA + INTERVAL_COLUMNS + ['Row Quality']]:
        raise ValueError(f'{path.name}: unexpected columns or interval order')
    frame = pd.read_csv(path, skiprows=skip, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    frame['source_line'] = np.arange(len(frame)) + skip + 2
    frame['source_file'] = path.name
    frame['date_raw'] = frame['date']
    dates = pd.to_datetime(frame['date'], format='%d-%b-%y', errors='coerce')
    alternate = pd.to_datetime(frame['date'], format='%d/%m/%Y', errors='coerce')
    frame['date'] = dates.fillna(alternate)
    for field in ['Customer', 'Generator Capacity', 'Postcode'] + INTERVAL_COLUMNS:
        frame[field] = pd.to_numeric(frame[field], errors='coerce')
    if 'Row Quality' not in frame:
        frame['Row Quality'] = ''
    return frame
