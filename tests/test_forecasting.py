import numpy as np
import pandas as pd
import pytest

from solarshift.features.dataset import build_channel, FEATURE_COLUMNS, AVAILABILITY_COLUMNS, assert_available, assign_split
from solarshift.features.build import select_cohort
from solarshift.models.persistence import predict
from solarshift.evaluation.metrics import errors, evening_mask, aggregate_complete_days


@pytest.fixture
def forecast_config():
    return {'timezone': 'Australia/Sydney', 'issue_hour': 18, 'observation_delay_minutes': 30,
            'train_start': '2011-12-01', 'train_end': '2011-12-31',
            'validation_start': '2012-01-01', 'validation_end': '2012-02-29',
            'test_start': '2012-03-01', 'test_end': '2012-03-31',
            'cohort_size': 2, 'cohort_seed': 2112, 'minimum_training_coverage': 0.95}


def observations(start='2011-12-01', end='2012-02-10'):
    days = pd.date_range(start, end)
    dates = pd.Series(np.repeat(days, 48))
    slots = np.tile(np.arange(1, 49), len(days))
    endings = (dates + pd.to_timedelta(slots * 30, unit='m')).dt.tz_localize('Australia/Sydney')
    return pd.DataFrame({'customer': 1, 'channel': 'GC', 'source_date': dates, 'slot': slots,
                         'capacity_kwp': 3.0, 'interval_end': endings,
                         'interval_start': endings - pd.Timedelta(minutes=30),
                         'energy_kwh': np.repeat(np.arange(len(days)), 48) / 10 + slots / 100})


def target(frame, day='2012-01-10'):
    return frame[frame.source_date.eq(day)].reset_index(drop=True)


def test_weekly_baseline_uses_calendar_date_and_48_outputs(forecast_config):
    original = observations()
    built, _ = build_channel(original, forecast_config)
    example = target(built)
    expected = original[original.source_date.eq('2012-01-03')].energy_kwh.to_numpy()
    assert len(example) == 48
    np.testing.assert_array_equal(predict(example), expected)
    assert set(example.split) == {'validation'}


def test_actuals_after_issue_time_cannot_change_features(forecast_config):
    source = observations()
    before, _ = build_channel(source, forecast_config)
    issue = pd.Timestamp('2012-01-09 18:00', tz='Australia/Sydney')
    source.loc[source.interval_end + pd.Timedelta(minutes=30) > issue, 'energy_kwh'] += 10000
    after, _ = build_channel(source, forecast_config)
    pd.testing.assert_frame_equal(target(before)[FEATURE_COLUMNS + AVAILABILITY_COLUMNS],
                                  target(after)[FEATURE_COLUMNS + AVAILABILITY_COLUMNS])
    assert not target(before).energy_kwh.equals(target(after).energy_kwh)


def test_previous_day_availability_boundary_and_fallback(forecast_config):
    frame, _ = build_channel(observations(), forecast_config)
    sample = target(frame).set_index('slot')
    assert sample.loc[35, 'previous_day_available'] == 1  # 17:30 + 30 min = 18:00
    assert sample.loc[36, 'previous_day_available'] == 0  # 18:00 reading arrives at 18:30
    assert sample.loc[36, 'previous_day_or_2d_kwh'] == sample.loc[36, 'lag_2d_kwh']
    assert sample.loc[35, 'previous_day_or_2d_available_at'] == sample.loc[35, 'issued_at']


def test_rolling_mean_has_exactly_seven_past_days(forecast_config):
    source = observations()
    frame, _ = build_channel(source, forecast_config)
    expected = source[source.source_date.between('2012-01-02', '2012-01-08') & source.slot.eq(40)].energy_kwh.mean()
    assert target(frame).set_index('slot').loc[40, 'rolling_7d_kwh'] == pytest.approx(expected)


def test_missing_calendar_day_does_not_shift_history(forecast_config):
    source = observations()
    source = source[~source.source_date.eq('2012-01-03')]
    frame, ledger = build_channel(source, forecast_config)
    assert target(frame).empty
    assert ledger.source_date.eq('2012-01-10').any()


def test_one_missing_interval_excludes_entire_forecast_day(forecast_config):
    source = observations()
    source = source[~(source.source_date.eq('2012-01-10') & source.slot.eq(48))]
    frame, _ = build_channel(source, forecast_config)
    assert target(frame).empty


@pytest.mark.parametrize('column', AVAILABILITY_COLUMNS)
def test_leakage_guard_checks_every_observed_feature(forecast_config, column):
    frame, _ = build_channel(observations(), forecast_config)
    frame.loc[frame.index[0], column] = frame.iloc[0].issued_at + pd.Timedelta(seconds=1)
    with pytest.raises(ValueError, match='leakage'):
        assert_available(frame)


def test_duplicate_history_rejected(forecast_config):
    source = observations()
    with pytest.raises(ValueError, match='Duplicate'):
        build_channel(pd.concat([source, source.iloc[[0]]]), forecast_config)


def test_partition_boundaries_and_reserved_test(forecast_config):
    dates = pd.Series(pd.to_datetime(['2011-11-30', '2011-12-01', '2011-12-31', '2012-01-01', '2012-02-29', '2012-03-01']))
    assert assign_split(dates, forecast_config).tolist() == ['outside', 'train', 'train', 'validation', 'validation', 'test']
    frame, _ = build_channel(observations(end='2012-03-15'), forecast_config)
    assert set(frame.split) == {'train', 'validation'}
    assert frame.source_date.max() == pd.Timestamp('2012-02-29')


def test_overlap_rejected(forecast_config):
    forecast_config['validation_start'] = '2011-12-31'
    with pytest.raises(ValueError, match='non-overlapping'):
        assign_split(pd.Series(pd.to_datetime(['2012-01-01'])), forecast_config)


def test_quarantined_dst_day_remains_missing_in_lag_window(forecast_config):
    # 1 April 2012 is a Sydney DST transition: it is absent from cleaned data.
    source = pd.concat([observations('2012-03-15', '2012-03-31'),
                        observations('2012-04-02', '2012-04-20')], ignore_index=True)
    forecast_config.update(train_start='2012-03-15', train_end='2012-03-31',
                           validation_start='2012-04-01', validation_end='2012-04-30',
                           test_start='2012-05-01', test_end='2012-05-31')
    frame, ledger = build_channel(source, forecast_config)
    assert target(frame, '2012-04-08').empty
    assert ledger.source_date.eq('2012-04-08').any()
    sample = target(frame, '2012-04-10')
    assert len(sample) == 48
    assert sample.iloc[0].issued_at.utcoffset().total_seconds() == 10 * 3600


def test_cohort_selection_ignores_validation_and_future_coverage(forecast_config):
    data = pd.MultiIndex.from_product([[1, 2, 3], pd.date_range('2011-12-01', '2011-12-31'), ['GC', 'GG']],
                                      names=['customer', 'source_date', 'channel']).to_frame(index=False)
    chosen, _ = select_cohort(data, forecast_config)
    future = data.copy(); future['source_date'] += pd.Timedelta(days=80); future['customer'] = 999
    assert select_cohort(pd.concat([data, future]), forecast_config)[0] == chosen
    assert select_cohort(data.sample(frac=1, random_state=42), forecast_config)[0] == chosen


def test_mae_rmse_and_units():
    result = errors([1, 2], [2, 4])
    assert result == {'n': 2, 'mae_kwh': 1.5, 'rmse_kwh': np.sqrt(2.5)}


@pytest.mark.parametrize(('actual', 'predicted'), [([], []), ([1], [1, 2]), ([np.nan], [1]), ([[1]], [[1]])])
def test_invalid_metric_inputs_fail(actual, predicted):
    with pytest.raises(ValueError):
        errors(actual, predicted)


def test_evening_window_uses_start_time_and_ten_intervals():
    frame = observations(end='2011-12-01')
    peak = frame[evening_mask(frame)]
    assert peak.slot.tolist() == list(range(33, 43))
    assert peak.iloc[0].interval_start.hour == 16
    assert peak.iloc[-1].interval_end.hour == 21


def test_community_metrics_require_fixed_complete_cohort():
    first = observations(end='2011-12-02').rename(columns={'energy_kwh': 'actual_kwh'})
    first['predicted_kwh'] = first.actual_kwh + 0.1
    second = first.copy(); second['customer'] = 2; second['predicted_kwh'] = second.actual_kwh - 0.1
    # Missing just one household-slot must remove the whole community day.
    second = second[~(second.source_date.eq('2011-12-02') & second.slot.eq(48))]
    combined = aggregate_complete_days(pd.concat([first, second]), 2)
    assert len(combined) == 48
    assert combined.source_date.nunique() == 1
    assert errors(combined.actual_kwh, combined.predicted_kwh)['mae_kwh'] < 1e-12
