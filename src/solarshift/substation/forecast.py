"""Common validation replay interface for the Day 5/6 dashboard."""
from pathlib import Path
import pandas as pd

COLUMNS = ['site', 'date', 'issue_time', 'interval_start', 'interval_end', 'hh',
           'signed_actual_mw', 'actual_magnitude_mw', 'q10_mw', 'q50_mw', 'q90_mw',
           'split', 'weather_provenance', 'quality_flags', 'anomaly',
           'weekly_mw', 'yesterday_mw', 'weather_calendar_mw']


def validation_forecast(directory: str | Path, site: str, date: str) -> pd.DataFrame:
    """Return one COMPLETE 48-slot replay; fail clearly on gaps or test requests.

    Actuals are included for historical replay only, never as model features.
    """
    date = pd.Timestamp(date)
    if date.tzinfo is not None or date != date.normalize():
        raise ValueError('Use a local calendar date without time or timezone')
    if not pd.Timestamp('2023-05-01') <= date < pd.Timestamp('2024-05-01'):
        raise ValueError('Only validation dates are available; reserved test is disabled')
    p = Path(directory) / 'validation_forecasts.parquet'
    f = pd.read_parquet(p, columns=COLUMNS,
                        filters=[('site', '=', site), ('date', '=', date)])
    f = f.sort_values('hh').reset_index(drop=True)
    if f.hh.tolist() != list(range(48)):
        raise ValueError(f'Complete forecast unavailable for {site} on {date.date()}: {len(f)}/48 eligible slots')
    if not f.split.eq('val').all() or not f.quality_flags.eq(0).all():
        raise ValueError('Invalid validation artifact')
    return f
