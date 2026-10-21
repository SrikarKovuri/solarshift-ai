"""Conservative whole-channel-day exclusion with an explicit reason ledger."""

import numpy as np
import pandas as pd

from .parse import INTERVAL_COLUMNS


def dst_dates(dates: pd.Series) -> set:
    days = pd.DatetimeIndex(dates.dropna().unique())
    starts = days.tz_localize('Australia/Sydney')
    ends = (days + pd.Timedelta(days=1)).tz_localize('Australia/Sydney')
    return set(days[(ends - starts) != pd.Timedelta(hours=24)])


def validate(frame: pd.DataFrame, start: str | None = None, end: str | None = None):
    reasons = pd.Series('', index=frame.index)

    def flag(mask, reason):
        reasons.loc[mask] = reasons.loc[mask] + reason + ';'

    values = frame[INTERVAL_COLUMNS].to_numpy(dtype=float)
    flag(frame['date'].isna(), 'invalid_date')
    customer = frame['Customer']
    flag(customer.isna() | ~customer.between(1, 300) | (customer % 1 != 0), 'invalid_customer')
    postcode = frame['Postcode']
    flag(postcode.isna() | ~postcode.between(1000, 9999) | (postcode % 1 != 0), 'invalid_postcode')
    capacity = frame['Generator Capacity']
    flag(~np.isfinite(capacity) | (capacity <= 0), 'invalid_capacity')
    flag(~frame['Consumption Category'].isin(['GC', 'GG', 'CL']), 'invalid_channel')
    flag(frame['Row Quality'].str.strip() != '', 'non_actual_or_unknown_quality')
    flag(~np.isfinite(values).all(axis=1), 'missing_or_nonfinite_interval')
    flag((values < 0).any(axis=1), 'negative_interval')
    flag(frame.duplicated(['Customer', 'date', 'Consumption Category'], keep=False), 'duplicate_channel_day')
    flag(frame['date'].isin(dst_dates(frame['date'])), 'dst_transition_day')
    if start and end:
        flag(frame['date'].notna() & ~frame['date'].between(start, end), 'outside_file_period')
    for field in ['Postcode', 'Generator Capacity']:
        inconsistent = frame.groupby('Customer')[field].transform('nunique') > 1
        flag(inconsistent, 'inconsistent_' + field.lower().replace(' ', '_'))
    accepted = frame.loc[reasons == ''].copy()
    excluded = frame.loc[reasons != '', ['source_file', 'source_line', 'Customer', 'date_raw', 'Consumption Category']].copy()
    excluded['reasons'] = reasons[reasons != ''].str.rstrip(';')
    counts = reasons[reasons != ''].str.rstrip(';').str.split(';').explode().value_counts().to_dict()
    high_pv = (frame['Consumption Category'].eq('GG').to_numpy() &
               (values > capacity.to_numpy()[:, None] * 0.5 * 1.25).any(axis=1))
    report = {'input_channel_days': len(frame), 'accepted_channel_days': len(accepted),
              'excluded_channel_days': len(excluded), 'exclusion_reasons': {k: int(v) for k, v in counts.items()},
              'warning_pv_days_above_125_percent_nameplate': int(high_pv.sum()),
              'warning_policy': 'Nameplate exceedance is flagged, not automatically excluded.'}
    return accepted, excluded, report


def to_intervals(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert accepted daily rows. Slot 48 ends at next midnight; DST dates are rejected."""
    if frame['date'].isin(dst_dates(frame['date'])).any():
        raise ValueError('Cannot construct 48 physical intervals on a DST transition day.')
    fields = ['Customer', 'Generator Capacity', 'Postcode', 'Consumption Category', 'date', 'source_file', 'source_line']
    result = frame.melt(id_vars=fields, value_vars=INTERVAL_COLUMNS, var_name='interval_label', value_name='energy_kwh')
    slot_map = {label: slot for slot, label in enumerate(INTERVAL_COLUMNS, 1)}
    result['slot'] = result.pop('interval_label').map(slot_map).astype('int8')
    naive = result['date'] + pd.to_timedelta(result['slot'].astype('int64') * 30, unit='m')
    result['interval_end'] = naive.dt.tz_localize('Australia/Sydney', ambiguous='raise', nonexistent='raise')
    result['interval_start'] = result['interval_end'] - pd.Timedelta(minutes=30)
    result['average_power_kw'] = result['energy_kwh'] / 0.5
    result = result.rename(columns={'Customer': 'customer', 'Generator Capacity': 'capacity_kwp',
                                    'Postcode': 'postcode', 'Consumption Category': 'channel', 'date': 'source_date'})
    result['customer'] = result['customer'].astype('int16')
    result['postcode'] = result['postcode'].astype('int16')
    result['energy_kwh'] = result['energy_kwh'].astype('float64')
    result['capacity_kwp'] = result['capacity_kwp'].astype('float64')
    return result
