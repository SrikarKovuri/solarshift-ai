"""Independently audit Day 4 source joins, predictions, units and metrics."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from xgboost import Booster, DMatrix
from solarshift.substation.pipeline import FEATURES, digest
from solarshift.substation.forecast import validation_forecast

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--directory', type=Path, default=Path('results/generated/substation_day4'))
a = p.parse_args()
d = a.directory
v = pd.read_parquet(d/'validation_forecasts.parquet')
c = pd.read_parquet(d/'clean_development.parquet')
assert v.date.between('2023-05-01','2024-04-30').all()
assert not v.duplicated(['site','date','hh']).any()
assert v.quality_flags.eq(0).all()
assert (v.weather_latest_issue_time < v.issue_time).all()
assert (v.latest_load_available_at <= v.issue_time).all()
assert (v.interval_end - v.interval_start).eq(pd.Timedelta(minutes=30)).all()
actual = v.merge(c[['substation','date','hh','mw','mw_published']], on=['substation','date','hh'], validate='one_to_one', suffixes=('','_source'))
np.testing.assert_allclose(actual.actual_magnitude_mw, actual.mw, atol=1e-6)
np.testing.assert_allclose(actual.signed_actual_mw, actual.mw_published_source, atol=1e-6)
# Independently join exact previous dates, rather than trusting saved lag features.
for lag,col in [(1,'yesterday_mw'),(7,'weekly_mw')]:
    history = c[['substation','date','hh','mw']].copy()
    history['date'] += pd.Timedelta(days=lag)
    joined = v.merge(history,on=['substation','date','hh'],validate='one_to_one')
    np.testing.assert_allclose(joined[col],joined.mw,atol=1e-6)
# Reload native boosters; inverse scale and quantile rearrangement checked separately.
sample = v.iloc[::max(1,len(v)//10000)]
raw = []
for q in [10,50,90]:
    m = Booster()
    m.load_model(d/f'q{q}.ubj')
    raw.append(m.predict(DMatrix(sample[FEATURES])))
pred = np.sort(np.maximum(np.column_stack(raw),0),axis=1) * sample.level_mw.to_numpy()[:,None]
np.testing.assert_allclose(pred,sample[['q10_mw','q50_mw','q90_mw']],atol=1e-6)
for _, row in pd.read_csv(d/'metrics.csv').iterrows():
    b = v[v.hh.between(32,41)] if row.window == 'evening' else v
    col = {'weekly':'weekly_mw','yesterday':'yesterday_mw','weather_calendar':'weather_calendar_mw','quantile_boosted':'q50_mw'}[row.model]
    e = b[col].to_numpy() - b.actual_magnitude_mw.to_numpy()
    np.testing.assert_allclose([np.mean(abs(e)),np.sqrt(np.mean(e**2))], [row.mae_mw,row.rmse_mw],rtol=1e-10)
    assert len(b) == row.n
complete = v.groupby(['site','date']).size()
site,date = complete[complete == 48].index[0]
f = validation_forecast(d,site,str(date.date()))
assert len(f) == 48
out = {'passed':True,'validation_rows':len(v),'model_reload_sample_rows':len(sample),
       'complete_site_days':int((complete == 48).sum()),'example_site':site,'example_date':str(date.date()),
       'checks':['source actuals','calendar-day persistence','MW inverse scale','quantile reload',
                 'common eligible metrics','issue-time bounds','30-minute intervals','complete replay interface'],
       'artifact_hashes':{p.name:digest(p) for p in d.iterdir() if p.suffix in ['.parquet','.ubj','.csv','.json'] and p.name != 'audit.json'}}
(d/'audit.json').write_text(json.dumps(out,indent=2))
print(json.dumps({k:x for k,x in out.items() if k != 'artifact_hashes'},indent=2))
