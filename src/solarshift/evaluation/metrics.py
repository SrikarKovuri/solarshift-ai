import numpy as np


def errors(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if actual.ndim != 1 or actual.shape != predicted.shape or not actual.size:
        raise ValueError('Expected equally sized, non-empty one-dimensional arrays')
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError('Metrics cannot silently ignore non-finite observations')
    difference = predicted - actual
    return {'n': int(actual.size), 'mae_kwh': float(np.abs(difference).mean()),
            'rmse_kwh': float(np.sqrt(np.square(difference).mean()))}


def evening_mask(frame):
    # Start-time window includes 16:00–16:30, ends with 20:30–21:00.
    local = frame['interval_start'].dt.tz_convert('Australia/Sydney')
    return (local.dt.hour >= 16) & (local.dt.hour < 21)


def aggregate_complete_days(frame, cohort_size):
    if frame.duplicated(['customer', 'channel', 'source_date', 'slot']).any():
        raise ValueError('Duplicate forecast key before community aggregation')
    aggregate = frame.groupby(['channel', 'source_date', 'slot'], as_index=False).agg(
        actual_kwh=('actual_kwh', 'sum'), predicted_kwh=('predicted_kwh', 'sum'),
        households=('customer', 'nunique'), interval_start=('interval_start', 'first'))
    complete_slot = aggregate.households == cohort_size
    complete_day = complete_slot.groupby([aggregate.channel, aggregate.source_date]).transform('all')
    count = aggregate.groupby(['channel', 'source_date'])['slot'].transform('count')
    return aggregate[complete_day & (count == 48)].copy()
