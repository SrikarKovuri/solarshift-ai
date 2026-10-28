"""Day 4 validation-only integration, adapted from Theo's supplied pipeline.

Raw data remains in the supplied folder. No FY2025 load file is opened.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import io
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from . import ausgrid, calendar_nsw, selection

TRAIN_START = pd.Timestamp('2021-05-01')
VAL_START = pd.Timestamp('2023-05-01')
TEST_START = pd.Timestamp('2024-05-01')
SPRING = pd.to_datetime(['2021-10-03', '2022-10-02', '2023-10-01'])
AUTUMN = pd.to_datetime(['2021-04-04', '2022-04-03', '2023-04-02', '2024-04-07'])
GROUPS = {
    'calendar': ['hh_sin', 'hh_cos', 'dow', 'month', 'doy_sin', 'doy_cos', 'holiday', 'is_dst'],
    'historical_load': ['lag_d1', 'lag_d7', 'lag_d14', 'same_hh_mean7', 'prev_day_mean', 'prev_eve_mean'],
    'forecast_weather': ['temp', 'tmax', 'tmin', 'tmean'],
    'sun_position': ['sun_elev'],
    'training_attributes': ['level_log', 'evening_share', 'lat', 'lon'],
}
FEATURES = sum(GROUPS.values(), [])
PARAMS = dict(n_estimators=240, max_depth=5, learning_rate=0.05,
              min_child_weight=50, subsample=0.8, colsample_bytree=0.8,
              tree_method='hist', n_jobs=4, random_state=2112)


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def guard_development(frame):
    if frame['date'].isna().any() or (frame['date'] >= TEST_START).any():
        raise ValueError('Reserved test dates or missing dates are forbidden')
    if 'split' in frame and not frame['split'].isin(['train', 'val']).all():
        raise ValueError('Only training and validation splits allowed')


def clean_wide(w):
    """Fit spike scale only on training; exclude entire ambiguous DST days.

    Flags: 1 missing, 2 spike, 4 >=4-hour flat run, 8 DST day.
    No imputation. Preserve published sign; abs is applied AFTER averaging.
    """
    w = w.sort_values(['substation', 'date']).reset_index(drop=True)
    guard_development(w)
    if w.duplicated(['substation', 'date']).any():
        raise ValueError('Duplicate site/date')
    if not w.unit.str.upper().eq('MW').all():
        raise ValueError('Expected MW units')
    x = w[list(range(96))].to_numpy(float)
    flags = np.where(np.isfinite(x), 0, 1).astype('uint8')
    scales = []
    for site, idx in w.groupby('substation').indices.items():
        train_idx = idx[w.loc[idx, 'date'].between(TRAIN_START, VAL_START, inclusive='left')]
        delta = np.diff(x[train_idx], axis=1)
        med = np.nanmedian(delta)
        mad = 1.4826 * np.nanmedian(np.abs(delta - med)) + 1e-6
        scales.append(dict(substation=site, change_median=med, change_scale=mad))
        d = np.diff(x[idx], axis=1)
        z = np.abs(d - med) / mad
        spike = (z[:, :-1] > 15) & (z[:, 1:] > 15) & (np.sign(d[:, :-1]) != np.sign(d[:, 1:]))
        block = flags[idx].copy()
        block[:, 1:-1] |= spike.astype('uint8') * 2
        flags[idx] = block
    run = np.zeros(len(w), dtype=int)
    for j in range(1, 96):
        run = np.where(np.isfinite(x[:, j]) & (x[:, j] == x[:, j-1]), run + 1, 0)
        hit = run >= 15
        flags[hit, j-15:j+1] |= 4
    dst = w.date.isin(SPRING.union(AUTUMN)).to_numpy()
    flags[dst] |= 8
    x[flags > 0] = np.nan
    hh = x.reshape(-1, 48, 2).mean(2)
    hflags = np.bitwise_or.reduce(flags.reshape(-1, 48, 2), axis=2)
    out = pd.DataFrame({'substation': np.repeat(w.substation.to_numpy(), 48),
                        'date': np.repeat(w.date.to_numpy(), 48),
                        'hh': np.tile(np.arange(48, dtype='int8'), len(w)),
                        'mw_published': hh.ravel().astype('float32'),
                        'quality_flags': hflags.ravel(),
                        'dst_change_day': np.repeat(dst, 48)})
    out['mw'] = out.mw_published.abs()
    out['sign_available'] = out.date >= VAL_START
    return out, pd.DataFrame(scales)


def read_development(source):
    frames = []
    for year in range(2021, 2025):
        print(f'Reading FY{year}', flush=True)
        w = ausgrid.read_year_wide(source / 'data/raw/ausgrid' / f'ausgrid_zss_FY{year}.zip')
        if w.date.isna().any():
            raise ValueError('Unparseable source date')
        w['date'] = pd.to_datetime(w.date)
        w = w[w.date.between('2021-04-01', '2024-04-30')].copy()
        w['substation'] = w.substation.map(ausgrid.canonical_name)
        frames.append(w)
    return clean_wide(pd.concat(frames, ignore_index=True))


def select_cohort(long, source):
    train = long[long.date.between(TRAIN_START, VAL_START, inclusive='left')]
    cov = train.groupby('substation').mw.count() / (730 * 48)
    candidates = cov[cov >= .90].index
    shapes = selection.shape_vectors(long, candidates)
    km, k, scores = selection.cluster_shapes(shapes)
    desc, clusters = selection.describe_clusters(shapes, km.labels_)
    candidates_res = clusters[clusters.residential_like]
    if candidates_res.empty:
        raise ValueError('No residential-like training cluster')
    residential = (candidates_res.evening_peak / candidates_res.midday).idxmax()
    sel = desc[desc.cluster.eq(residential)].reset_index()
    anomaly = selection.anomaly_days(long, sel.substation)
    atr = anomaly[anomaly.date.between(TRAIN_START, VAL_START, inclusive='left')]
    fractions = atr.groupby('substation').anomaly.mean()
    sel['anomaly_fraction_train'] = sel.substation.map(fractions)
    sel = sel[sel.anomaly_fraction_train < .05].copy()
    # Read coordinates only: supplied cohort classifications/coverage are not used.
    loc = pd.read_csv(source / 'data/processed/substation_locations.csv')
    sel['base_name'] = sel.substation.str.replace(r'\s+\d.*$', '', regex=True)
    sel = sel.merge(loc, on='base_name', how='left', validate='many_to_one')
    if sel[['lat', 'lon', 'weather_zone']].isna().any().any():
        raise ValueError('Missing coordinates for training-selected sites')
    sel['cov_train'] = sel.substation.map(cov)
    val = long[long.date >= VAL_START].groupby('substation').mw.count() / (366 * 48)
    sel['cov_val_descriptive_only'] = sel.substation.map(val)
    return sel, anomaly, {'k': k, 'silhouette': {int(k): float(v) for k, v in scores.items()}, 'candidate_count': len(candidates),
                           'clusters': clusters.reset_index().to_dict('records')}


def read_weather(path):
    """Only cached genuine 24h-lead temperature; no donors, oracle or interpolation."""
    body = path.read_text().split('\n\n', 1)[1]
    w = pd.read_csv(io.StringIO(body))
    w.columns = [c.split(' (')[0] for c in w.columns]
    w['valid_time'] = pd.to_datetime(w.time)
    w = w[w.valid_time < TEST_START].copy()
    w['date'] = w.valid_time.dt.normalize()
    w['hour'] = w.valid_time.dt.hour
    # Drop duplicated clock times; corresponding load DST days are excluded.
    w = w.drop_duplicates(['date', 'hour'], keep=False)
    w = w[['date', 'hour', 'temperature_2m_previous_day1']].rename(columns={'temperature_2m_previous_day1': 'temp'})
    d = w.groupby('date').temp.agg(tmax='max', tmin='min', tmean='mean', count='count')
    d.loc[d['count'] < 24, ['tmax', 'tmin', 'tmean']] = np.nan
    return w.merge(d.drop(columns='count'), on='date')


def site_features(g, site, weather):
    guard_development(g)
    return _site_features(g, site, weather, '2024-04-30')


def _site_features(g, site, weather, end):
    """Shared feature construction; callers enforce their authorised split."""
    days = pd.date_range('2021-04-01', end)
    m = g.pivot(index='date', columns='hh', values='mw').reindex(index=days, columns=range(48))
    training = m.loc['2021-05-01':'2023-04-30']
    level = float(training.stack().mean())
    if not np.isfinite(level) or level <= 0:
        raise ValueError('Nonpositive training level')
    y = m / level
    f = pd.DataFrame({'date': np.repeat(days, 48), 'hh': np.tile(np.arange(48), len(days))})
    f['substation'] = site['substation']
    f['y'] = y.to_numpy().ravel()
    for lag in (1, 7, 14):
        f[f'lag_d{lag}'] = y.shift(lag).to_numpy().ravel()
    f['same_hh_mean7'] = y.shift(1).rolling(7, min_periods=4).mean().to_numpy().ravel()
    f['prev_day_mean'] = np.repeat(y.mean(axis=1).shift(1), 48).to_numpy()
    f['prev_eve_mean'] = np.repeat(y.iloc[:, 32:42].mean(axis=1).shift(1), 48).to_numpy()
    f['level_mw'] = level
    f['level_log'] = np.log(level)
    f['evening_share'] = float(training.iloc[:, 32:42].stack().mean() / level)
    f['lat'], f['lon'] = site['lat'], site['lon']
    f['hh_sin'] = np.sin(2*np.pi*f.hh/48)
    f['hh_cos'] = np.cos(2*np.pi*f.hh/48)
    f['dow'], f['month'] = f.date.dt.dayofweek, f.date.dt.month
    f['doy_sin'] = np.sin(2*np.pi*f.date.dt.dayofyear/365.25)
    f['doy_cos'] = np.cos(2*np.pi*f.date.dt.dayofyear/365.25)
    f['holiday'] = f.date.dt.date.isin(calendar_nsw.NSW_HOLIDAYS_FALLBACK).astype(int)
    dst = {d: int((d+pd.Timedelta(hours=12)).tz_localize('Australia/Sydney').dst().total_seconds() > 0) for d in days}
    f['is_dst'] = f.date.map(dst)
    f['sun_elev'] = calendar_nsw.solar_elevation_deg(pd.DatetimeIndex(f.date + pd.to_timedelta(f.hh*30+15, unit='min')), site['lat'], site['lon'])
    f['hour'] = f.hh // 2
    f = f.merge(weather, on=['date', 'hour'], how='left', validate='many_to_one')
    f = f.merge(g[['date', 'hh', 'mw_published', 'quality_flags', 'sign_available']], on=['date', 'hh'], how='left', validate='one_to_one')
    f = f[f.date >= TRAIN_START].copy()
    f['split'] = np.where(f.date < VAL_START, 'train', 'val')
    f['issue_time'] = f.date.dt.tz_localize('Australia/Sydney')
    f['interval_start'] = (f.date + pd.to_timedelta(f.hh*30, unit='min')).dt.tz_localize('Australia/Sydney', ambiguous='NaT', nonexistent='NaT')
    f['interval_end'] = f.interval_start + pd.Timedelta(minutes=30)
    f['latest_load_available_at'] = f.issue_time
    # Previous-day1 is 24 elapsed hours before each valid hour (source documentation).
    f['weather_latest_issue_time'] = (f.date + pd.Timedelta(hours=23)).dt.tz_localize('Australia/Sydney') - pd.Timedelta(hours=24)
    f['weather_provenance'] = 'cached_gfs_previous_day1_temperature_only'
    f['actual_magnitude_mw'] = f.y * level
    return f


def eligible_rows(f):
    guard_development(f)
    return (np.isfinite(f[FEATURES + ['y']]).all(axis=1) & f.interval_start.notna()
            & f.weather_latest_issue_time.lt(f.issue_time) & f.quality_flags.eq(0))


def metrics(actual, pred, level):
    err = np.asarray(pred) - np.asarray(actual)
    return {'n': len(err), 'mae_mw': float(np.mean(abs(err))),
            'rmse_mw': float(np.sqrt(np.mean(err**2))),
            'nmae_training_level_pct': float(100*np.mean(abs(err)/np.asarray(level)))}


def run(source, output, reuse_clean=False):
    started = time.time()
    output.mkdir(parents=True, exist_ok=True)
    used = [source / 'data/raw/ausgrid' / f'ausgrid_zss_FY{y}.zip' for y in range(2021, 2025)]
    used += sorted((source / 'src').glob('*.py'))
    used += [source/'reports'/n for n in ['data_dictionary.md', 'data_sources.md', 'preregistration.md']]
    used += [source/'data/processed/substation_locations.csv']
    used += sorted((source/'data/raw/weather').glob('*__gfs_dayahead.csv'))
    manifest = {str(p.relative_to(source)): digest(p) for p in used}
    (output/'source_manifest.json').write_text(json.dumps(manifest, indent=2))
    if reuse_clean:
        long = pd.read_parquet(output/'clean_development.parquet')
        guard_development(long)
    else:
        long, scales = read_development(source)
        long.to_parquet(output/'clean_development.parquet', index=False)
        scales.to_csv(output/'training_cleaning_scales.csv', index=False)
    print('Selecting cohort on training only', flush=True)
    sel, anomaly, cluster = select_cohort(long, source)
    sel.to_csv(output/'cohort.csv', index=False)
    anomaly.to_parquet(output/'anomaly_days.parquet', index=False)
    (output/'clustering.json').write_text(json.dumps(cluster, indent=2))
    print(f'Building features for {len(sel)} sites', flush=True)
    wx = {z: read_weather(source/'data/raw/weather'/f'openmeteo_{z}__gfs_dayahead.csv') for z in sel.weather_zone.unique()}
    frames = [site_features(long[long.substation == s.substation], s, wx[s.weather_zone]) for _, s in sel.iterrows()]
    f = pd.concat(frames, ignore_index=True)
    f = f.merge(anomaly[['substation', 'date', 'anomaly']], on=['substation', 'date'], how='left', validate='many_to_one')
    f['anomaly'] = f.anomaly.fillna(False).astype(bool)
    eligible = eligible_rows(f)
    exclusions = f.assign(eligible=eligible).groupby(['substation', 'split']).agg(total=('y','size'), eligible=('eligible','sum')).reset_index()
    exclusions.to_csv(output/'eligibility.csv', index=False)
    f.to_parquet(output/'features_development.parquet', index=False)
    # Complete training evenings only: fixed MW thresholds for Day 5.
    eve = f[(f.split == 'train') & f.hh.between(32, 41)].groupby(['substation', 'date']).actual_magnitude_mw.agg(['mean','count'])
    thresholds = eve[eve['count'] == 10].groupby('substation')['mean'].quantile(.9)
    thresholds.rename('threshold_evening_mean_magnitude_mw').to_csv(output/'peak_thresholds_training.csv')
    tr = f[eligible & f.split.eq('train') & ~f.anomaly]
    va = f[eligible & f.split.eq('val')].copy()
    print(f'Fitting fixed model: {len(tr):,} train / {len(va):,} validation rows', flush=True)
    models = {}
    raw = []
    for q in (.1, .5, .9):
        print(f'Fitting q{int(q*100)}', flush=True)
        m = XGBRegressor(objective='reg:quantileerror', quantile_alpha=q, **PARAMS)
        m.fit(tr[FEATURES], tr.y)
        raw.append(m.predict(va[FEATURES]))
        m.save_model(output/f'q{int(q*100)}.ubj')
        models[q] = m
    raw = np.column_stack(raw)
    predictions = np.sort(np.maximum(raw, 0), axis=1) * va.level_mw.to_numpy()[:, None]
    for j, q in enumerate((10, 50, 90)):
        va[f'q{q}_mw'] = predictions[:, j]
    reg_features = GROUPS['calendar'] + GROUPS['forecast_weather'] + GROUPS['sun_position'] + GROUPS['training_attributes']
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=10))
    ridge.fit(tr[reg_features], tr.y)
    va['weather_calendar_mw'] = np.maximum(0, ridge.predict(va[reg_features])) * va.level_mw
    # Portable linear model with scaling, no pickle needed.
    sc, rg = ridge.steps[0][1], ridge.steps[1][1]
    (output/'ridge.json').write_text(json.dumps({'features': reg_features, 'mean': sc.mean_.tolist(), 'scale': sc.scale_.tolist(), 'coef': rg.coef_.tolist(), 'intercept': float(rg.intercept_)}, indent=2))
    va['weekly_mw'] = va.lag_d7 * va.level_mw
    va['yesterday_mw'] = va.lag_d1 * va.level_mw
    va['signed_actual_mw'] = va.mw_published
    va['site'] = va.substation
    va['quality_flags'] = va.quality_flags.astype('uint8')
    va.to_parquet(output/'validation_forecasts.parquet', index=False)
    rows = []
    for window, mask in [('full_day', np.ones(len(va), dtype=bool)), ('evening', va.hh.between(32,41))]:
        v = va.loc[mask]
        for name, col in [('weekly','weekly_mw'), ('yesterday','yesterday_mw'), ('weather_calendar','weather_calendar_mw'), ('quantile_boosted','q50_mw')]:
            rows.append(dict(window=window, model=name, **metrics(v.actual_magnitude_mw, v[col], v.level_mw)))
    pd.DataFrame(rows).to_csv(output/'metrics.csv', index=False)
    # Reload every model and independently verify serialization on an evenly spaced sample.
    sample = va.iloc[::max(1,len(va)//1000)]
    for q, m in models.items():
        restored = XGBRegressor()
        restored.load_model(output/f'q{int(q*100)}.ubj')
        np.testing.assert_allclose(restored.predict(sample[FEATURES]), m.predict(sample[FEATURES]), rtol=0, atol=1e-7)
    evening = va[va.hh.between(32,41)]
    coverage = float(((evening.actual_magnitude_mw >= evening.q10_mw) & (evening.actual_magnitude_mw <= evening.q90_mw)).mean())
    sign = long.assign(period=np.where(long.date < VAL_START, 'before_May_2023', 'from_May_2023'))
    sign = sign.groupby('period').mw_published.agg(valid='count', negative=lambda x: int((x < 0).sum()))
    sign.to_csv(output/'sign_audit.csv')
    summary = dict(status='validation_only', sites=len(sel), train_rows=len(tr), validation_rows=len(va),
                   evening_raw_80pct_coverage=coverage, quantile_crossing_fraction=float(np.any(np.diff(raw,axis=1)<0,axis=1).mean()),
                   reserved_test_opened=False, duration_seconds=time.time()-started,
                   features=GROUPS, parameters=PARAMS, reload_verified=True,
                   availability_contract='Zero-latency load through D midnight; weather valid-hour minus 24h, latest D-1 23:00. Historical replay assumption, not operational latency validation.',
                   versions={n: importlib.metadata.version(n) for n in ['numpy','pandas','scikit-learn','xgboost','pyarrow']},
                   implementation_hashes={p.name:digest(p) for p in Path(__file__).parent.glob('*.py')})
    (output/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k not in ['features','versions','implementation_hashes']}, indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('results/generated/substation_day4'))
    p.add_argument('--reuse-clean', action='store_true', help='Reuse locally verified cleaned development table')
    args = p.parse_args()
    run(args.source.resolve(), args.output.resolve(), args.reuse_clean)

if __name__ == '__main__':
    main()
