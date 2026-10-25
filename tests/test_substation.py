"""Synthetic correctness tests, not performance evidence."""
import csv
import io
import numpy as np
import pandas as pd
import pytest
from solarshift.substation import ausgrid
from solarshift.substation.pipeline import FEATURES, clean_wide, guard_development, site_features, read_weather, eligible_rows


def test_scrambled_interval_end_labels():
    order = np.roll(np.arange(96), 13)
    labels = [f'{(i+1)*15//60:02d}:{(i+1)*15%60:02d}' for i in order]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['year','site','Date','Unit'] + labels)
    writer.writerow([2025,'Sample','2024-05-01','MW'] + [int(i) for i in order])
    row = ausgrid.read_csv_bytes(buf.getvalue().encode()).iloc[0]
    np.testing.assert_equal(row[list(range(96))].to_numpy(float), np.arange(96))


def wide_fixture():
    dates = pd.to_datetime(['2022-05-01','2022-05-02','2023-05-01','2023-10-01','2024-04-07'])
    w = pd.DataFrame(np.tile(5+np.sin(np.arange(96)/6), (len(dates),1)))
    w['date'], w['substation'], w['unit'] = dates, 'Sample', 'MW'
    return w


def test_signed_pair_mean_missing_dst_flat_and_spike():
    w = wide_fixture()
    w.loc[2, [0,1]] = [-3,-5]
    w.loc[2, 2] = np.nan
    w.loc[2, list(range(20,36))] = 4
    w.loc[2, 70] = 10000
    clean, _ = clean_wide(w)
    val = clean[clean.date == pd.Timestamp('2023-05-01')].set_index('hh')
    assert val.loc[0,'mw_published'] == -4
    assert val.loc[0,'mw'] == 4
    assert val.loc[0,'mw'] * .5 == 2
    assert np.isnan(val.loc[1,'mw'])
    assert val.loc[10,'quality_flags'] & 4
    assert val.loc[35,'quality_flags'] & 2
    assert clean.loc[clean.dst_change_day,'mw'].isna().all()


def test_cleaner_training_scale_independent_of_validation():
    w = wide_fixture()
    _, before = clean_wide(w)
    w.loc[w.date >= '2023-05-01', list(range(96))] *= 500
    _, after = clean_wide(w)
    pd.testing.assert_frame_equal(before, after)


def test_reject_test_dates_duplicates_and_wrong_units():
    with pytest.raises(ValueError, match='Reserved'):
        guard_development(pd.DataFrame({'date':pd.to_datetime(['2024-05-01'])}))
    w = wide_fixture()
    with pytest.raises(ValueError, match='Duplicate'):
        clean_wide(pd.concat([w,w]))
    w['unit'] = 'kWh'
    with pytest.raises(ValueError, match='MW'):
        clean_wide(w)


def feature_fixture():
    days = pd.date_range('2021-04-01','2024-04-30')
    g = pd.DataFrame({'date':np.repeat(days,48), 'hh':np.tile(np.arange(48),len(days))})
    g['mw'] = 5 + np.sin(np.arange(len(g))/19)
    g['mw_published'] = g.mw
    g['quality_flags'] = 0
    g['sign_available'] = g.date >= '2023-05-01'
    wx = pd.DataFrame({'date':np.repeat(days,24), 'hour':np.tile(np.arange(24),len(days))})
    for col in ['temp','tmax','tmin','tmean']:
        wx[col] = 20.
    return g, {'substation':'Sample','lat':-33.8,'lon':151.1}, wx


def test_target_day_and_future_load_cannot_enter_features():
    g,site,wx = feature_fixture()
    original = site_features(g,site,wx)
    g.loc[g.date >= '2023-06-01',['mw','mw_published']] = 9999
    changed = site_features(g,site,wx)
    mask = original.date == '2023-06-01'
    pd.testing.assert_frame_equal(original.loc[mask,FEATURES], changed.loc[mask,FEATURES])
    ok = eligible_rows(original)
    assert (original.loc[ok,'weather_latest_issue_time'] < original.loc[ok,'issue_time']).all()


def test_lags_use_calendar_days():
    g,site,wx = feature_fixture()
    f = site_features(g[g.date != '2023-06-01'],site,wx)
    assert f.loc[f.date == '2023-06-02','lag_d1'].isna().all()
    assert not eligible_rows(f)[f.date == '2023-06-02'].any()


def test_weather_no_oracle_fill_and_test_exclusion(tmp_path):
    p = tmp_path/'weather.csv'
    p.write_text('metadata\nmetadata\n\ntime,temperature_2m_previous_day1 (°C),temperature_2m (°C)\n2023-05-01T00:00,,99\n2023-05-01T01:00,12,99\n2024-05-01T00:00,42,99\n')
    w = read_weather(p)
    assert len(w) == 2
    assert np.isnan(w.iloc[0].temp)
    assert w.tmean.isna().all()


def test_short_raw_row_marks_missing_last_quarter():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['year','site','Date','Unit'] + [f'{(i+1)*15//60:02d}:{(i+1)*15%60:02d}' for i in range(96)])
    writer.writerow([2023,'Sample','01MAY2022','MW'] + list(range(95)))
    assert np.isnan(ausgrid.read_csv_bytes(buf.getvalue().encode()).iloc[0][95])


def test_validation_interface_rejects_reserved_dates_before_reading(tmp_path):
    from solarshift.substation.forecast import validation_forecast
    with pytest.raises(ValueError, match='reserved test'):
        validation_forecast(tmp_path, 'Sample', '2024-05-01')
    with pytest.raises(ValueError, match='local calendar date'):
        validation_forecast(tmp_path, 'Sample', '2023-06-01T12:00')


def test_weather_after_target_day_does_not_change_target_features():
    g,site,wx = feature_fixture()
    before = site_features(g,site,wx)
    wx.loc[wx.date > '2023-06-01',['temp','tmax','tmin','tmean']] = 999
    after = site_features(g,site,wx)
    mask = before.date == '2023-06-01'
    pd.testing.assert_frame_equal(before.loc[mask,FEATURES], after.loc[mask,FEATURES])
