"""Independent checks against saved final predictions; never refits or reopens raw test."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from solarshift.substation.pipeline import digest

root=Path('results/generated');out=root/'final_evaluation'
s=json.loads((out/'summary.json').read_text());freeze=json.loads((out/'freeze.json').read_text())
assert digest(out/'freeze.json')==s['freeze_sha256']
for name,h in freeze['hashes'].items():assert digest(root/name)==h,name
v=pd.read_parquet(out/'test_forecasts.parquet')
assert not v.duplicated(['site','date','hh']).any()
assert v.split.eq('test').all() and v.date.between('2024-05-01','2025-04-29').all()
assert v.weather_latest_issue_time.lt(v.issue_time).all()
assert not v.date.isin(pd.to_datetime(['2024-10-06','2025-04-06'])).any()
assert (v[['q10_mw','q50_mw','q90_mw']].diff(axis=1).iloc[:,1:]>=0).all().all()
np.testing.assert_allclose(v.actual_magnitude_mw,abs(v.signed_actual_mw),atol=1e-6)
rows=pd.read_csv(out/'metrics.csv')
for r in rows.itertuples():
 f=v[v.hh.between(32,41)] if r.window=='evening' else v
 col=dict(weekly='weekly_mw',yesterday='yesterday_mw',weather_calendar='weather_calendar_mw',quantile_boosted='q50_mw')[r.model]
 err=f[col]-f.actual_magnitude_mw
 assert r.n==len(f)
 np.testing.assert_allclose([r.mae_mw,r.rmse_mw,r.nmae_training_level_pct],
   [abs(err).mean(),np.sqrt((err**2).mean()),100*(abs(err)/f.level_mw).mean()],rtol=1e-10)
e=v[v.hh.between(32,41)]
improvement=100*(1-abs(e.q50_mw-e.actual_magnitude_mw).mean()/abs(e.weekly_mw-e.actual_magnitude_mw).mean())
np.testing.assert_allclose(improvement,s['bootstrap']['improvement_pct'])
adj=s['cqr_adjustment_mw']
np.testing.assert_allclose(e.actual_magnitude_mw.between((e.q10_mw-adj).clip(lower=0),e.q90_mw+adj).mean(),s['intervals']['cqr_coverage'])
w=pd.read_csv(out/'warning_metrics.csv')
assert (w.tp+w.fp+w.fn+w.tn).eq(w.n).all()
sweep=pd.read_csv(out/'sensitivity.csv')
assert len(sweep)==96 and sweep.max_energy_error_mwh.max()<1e-8
assert sweep.loc[sweep.response.eq(0),'total_displaced_mwh'].eq(0).all()
report=dict(status='passed',rows=len(v),forecast_metrics_checked=len(rows),scenario_combinations=len(sweep),
 frozen_hashes_unchanged=True,prediction_sha256=digest(out/'test_forecasts.parquet'),
 checks=['date boundary','unique keys','weather availability','DST exclusion','sorted quantiles',
 'signed/magnitude agreement','all model/window errors','MAE improvement','CQR coverage','warning counts','energy conservation','zero response'])
(out/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
