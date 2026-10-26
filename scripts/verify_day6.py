"""Independent explanation/replay audit; never opens reserved observations."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from solarshift.substation.pipeline import digest
from solarshift.substation.dashboard import catalog
from solarshift.substation.scenario_replay import replay_scenario

root=Path(__file__).resolve().parents[1]
d4=root/'results/generated/substation_day4'
d5=root/'results/generated/substation_day5'
d6=root/'results/generated/substation_day6'
meta=json.loads((d6/'explanations.json').read_text())
for name,sha in meta['model_hashes'].items():
    assert digest(d4/name)==sha
assert digest(d4/'features_development.parquet')==meta['feature_artifact_sha256']
# Independently reconstruct eligible sample and compare its loss with saved forecasts.
f=pd.read_parquet(d4/'features_development.parquet',filters=[('date','>=',pd.Timestamp('2023-11-01')),('date','<',pd.Timestamp('2024-05-01'))])
features=sum(json.loads((d4/'summary.json').read_text())['features'].values(),[])
mask=np.isfinite(f[features+['y']]).all(axis=1)&f.interval_start.notna()&f.weather_latest_issue_time.lt(f.issue_time)&f.quality_flags.eq(0)&f.split.eq('val')&f.hh.between(32,41)
sample=f[mask].sample(n=meta['rows'],random_state=meta['seed'])
saved=pd.read_parquet(d4/'validation_forecasts.parquet',columns=['site','date','hh','q50_mw'])
sample=sample.merge(saved,left_on=['substation','date','hh'],right_on=['site','date','hh'],validate='one_to_one')
assert len(sample)==meta['rows']
mae=float(abs(sample.actual_magnitude_mw-sample.q50_mw).mean())
assert np.isclose(mae,meta['sample_evening_mae_mw'],atol=1e-8)
days=catalog(d4,d5)
reference=pd.read_csv(d5/'default_scenarios.csv')
assert set(map(tuple,days.to_numpy()))==set(map(tuple,reference[['site','date']].to_numpy()))
active=reference[reference.moved_mwh>0].iloc[0]
r=replay_scenario(d4,d5,active.site,active.date)
assert np.isclose(r['metrics']['total_displaced_mwh'],active.moved_mwh,atol=1e-7)
assert r['metrics']['max_energy_error_mwh'] < 1e-8
report=dict(status='passed',catalog_days=len(days),sites=days.site.nunique(),explanation_rows=len(sample),
            saved_forecast_sample_mae_mw=mae,active_example={'site':active.site,'date':active.date,'moved_mwh':r['metrics']['total_displaced_mwh']},
            reserved_test_opened=False)
(d6/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
