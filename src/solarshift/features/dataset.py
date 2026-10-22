"""Construct direct next-day features using explicitly dated historical observations."""

import numpy as np
import pandas as pd

FEATURE_COLUMNS = ['slot', 'weekday', 'weekend', 'month', 'season', 'slot_sin', 'slot_cos',
                   'weekday_sin', 'weekday_cos', 'month_sin', 'month_cos', 'capacity_kwp',
                   'lag_2d_kwh', 'lag_7d_kwh', 'rolling_7d_kwh',
                   'previous_day_or_2d_kwh', 'previous_day_available']
AVAILABILITY_COLUMNS = ['lag_2d_available_at', 'lag_7d_available_at',
                        'rolling_7d_available_at', 'previous_day_or_2d_available_at']


def assign_split(dates: pd.Series, config: dict) -> pd.Series:
    ranges = [(name, pd.Timestamp(config[f'{name}_start']), pd.Timestamp(config[f'{name}_end']))
              for name in ['train', 'validation', 'test']]
    for i, (_, start, end) in enumerate(ranges):
        if start > end or (i and start <= ranges[i - 1][2]):
            raise ValueError('Chronological partitions must be ordered and non-overlapping.')
    result = pd.Series('outside', index=dates.index)
    for name, start, end in ranges:
        result.loc[dates.between(start, end)] = name
    return result


def assert_available(frame: pd.DataFrame) -> None:
    for column in AVAILABILITY_COLUMNS:
        if frame[column].isna().any() or (frame[column] > frame['issued_at']).any():
            raise ValueError(f'Feature leakage or missing provenance in {column}')
    if (frame['issued_at'] >= frame['interval_start']).any():
        raise ValueError('Forecast must be issued before every target interval.')


def build_channel(observations: pd.DataFrame, config: dict):
    """Build one household/channel. Missing history excludes the entire forecast day.

    Inputs may include later measurements; all feature lookups use source dates
    and timestamp availability, never row-position shifts or actual target-day values.
    """
    if observations[['customer', 'channel']].drop_duplicates().shape[0] != 1:
        raise ValueError('build_channel expects exactly one household and one channel')
    if observations.duplicated(['source_date', 'slot']).any():
        raise ValueError('Duplicate historical date/slot key')
    source = observations.sort_values(['source_date', 'slot']).reset_index(drop=True)
    if source['capacity_kwp'].nunique() != 1:
        raise ValueError('Capacity must be constant within a household history')
    frame = source[['customer', 'channel', 'source_date', 'slot', 'capacity_kwp',
                    'interval_start', 'interval_end', 'energy_kwh']].copy()
    naive_issue = frame['source_date'] - pd.Timedelta(days=1) + pd.Timedelta(hours=config['issue_hour'])
    frame['issued_at'] = naive_issue.dt.tz_localize(config['timezone'], ambiguous='raise', nonexistent='raise')
    delay = pd.Timedelta(minutes=config['observation_delay_minutes'])
    index = pd.MultiIndex.from_frame(source[['source_date', 'slot']])
    energy = pd.Series(source['energy_kwh'].to_numpy(), index=index)
    available = pd.Series((source['interval_end'] + delay).array, index=index)
    lag_values, lag_times = {}, {}
    for days in range(1, 9):
        keys = pd.MultiIndex.from_arrays([frame['source_date'] - pd.Timedelta(days=days), frame['slot']])
        lag_values[days] = pd.Series(energy.reindex(keys).to_numpy(), index=frame.index)
        lag_times[days] = pd.Series(available.reindex(keys).array, index=frame.index)
    for days in [2, 7]:
        frame[f'lag_{days}d_kwh'] = lag_values[days]
        frame[f'lag_{days}d_available_at'] = lag_times[days]
    history = pd.concat([lag_values[d] for d in range(2, 9)], axis=1)
    frame['rolling_7d_kwh'] = history.mean(axis=1).where(history.notna().all(axis=1))
    # All seven same-slot observations must exist. The newest is two source dates ago.
    frame['rolling_7d_available_at'] = lag_times[2].where(history.notna().all(axis=1))
    known_previous = lag_values[1].notna() & (lag_times[1] <= frame['issued_at'])
    frame['previous_day_available'] = known_previous.astype('int8')
    frame['previous_day_or_2d_kwh'] = lag_values[1].where(known_previous, lag_values[2])
    frame['previous_day_or_2d_available_at'] = lag_times[1].where(known_previous, lag_times[2])
    frame['weekday'] = frame.source_date.dt.dayofweek.astype('int8')
    frame['weekend'] = (frame.weekday >= 5).astype('int8')
    frame['month'] = frame.source_date.dt.month.astype('int8')
    frame['season'] = ((frame.month % 12) // 3).astype('int8')  # summer=0, autumn=1, winter=2, spring=3
    for feature, period, offset in [('slot', 48, 1), ('weekday', 7, 0), ('month', 12, 1)]:
        frame[f'{feature}_sin'] = np.sin(2 * np.pi * (frame[feature] - offset) / period)
        frame[f'{feature}_cos'] = np.cos(2 * np.pi * (frame[feature] - offset) / period)
    frame['split'] = assign_split(frame.source_date, config)
    complete_features = np.isfinite(frame[FEATURE_COLUMNS].to_numpy(dtype=float)).all(axis=1)
    complete_day = frame.groupby('source_date')['slot'].transform('count') == 48
    eligible_day = pd.Series(complete_features, index=frame.index).groupby(frame.source_date).transform('all') & complete_day
    ledger = frame.loc[~eligible_day, ['customer', 'channel', 'source_date']].drop_duplicates()
    ledger['reason'] = 'incomplete_target_day_or_required_history'
    accepted = frame.loc[eligible_day & frame.split.isin(['train', 'validation'])].copy()
    assert_available(accepted)
    if not np.isfinite(accepted.energy_kwh).all():
        raise ValueError('Non-finite forecast targets')
    return accepted, ledger
