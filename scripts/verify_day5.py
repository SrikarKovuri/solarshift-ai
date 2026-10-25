"""Independent artifact audit: daily warnings and signed-flow scenario accounting."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from solarshift.substation.pipeline import digest
from solarshift.substation.scenario_replay import replay_scenario

p=Path('results/generated/substation_day5'); day4=Path('results/generated/substation_day4')
s=json.loads((p/'summary.json').read_text()); cal=json.loads((p/'calibration.json').read_text())
for n,h in s['input_hashes'].items():assert digest(day4/n)==h
warnings=pd.read_csv(p/'daily_warnings.csv',parse_dates=['date'])
eval=warnings[warnings.date>='2023-11-01']
assert warnings.loc[warnings.date<'2023-11-01','p_calibrated'].isna().all()
assert pd.Timestamp(cal['fit_end'])<eval.date.min()
np.testing.assert_allclose(eval.p_calibrated,np.interp(eval.p_raw,cal['x'],cal['y']))
expected=1+np.maximum(eval.p_calibrated.to_numpy()-.3,0)*(.5/.7)
np.testing.assert_allclose(eval.multiplier,expected)
for col in ['p_raw','p_calibrated']:
    assert abs(np.mean((eval[col]-eval.event.astype(int))**2)-s['brier'][col])<1e-12
scores=pd.read_csv(p/'warning_metrics.csv').set_index('rule')
e=eval.event.to_numpy(bool);w=eval.p_calibrated.to_numpy()>=.3
assert scores.loc['calibrated_probability_0.30','tp']==int((e&w).sum())
assert scores.loc['calibrated_probability_0.30','fp']==int((~e&w).sum())
curves=pd.read_parquet(p/'default_curves.parquet')
keys=['site','date']; before=curves.pivot(index=keys,columns='hh',values='before_signed_mw')
after=curves.pivot(index=keys,columns='hh',values='after_signed_mw').reindex(before.index)
x=before.to_numpy();y=after.to_numpy()
source=pd.read_parquet(day4/'validation_forecasts.parquet',columns=['site','date','hh','signed_actual_mw'])
original=source.pivot(index=keys,columns='hh',values='signed_actual_mw').reindex(before.index)
np.testing.assert_allclose(x,original)
energy_error=(y-x).sum(1)*.5
assert abs(energy_error).max()<1e-8
removed=(x[:,32:42]-y[:,32:42]).sum(1)*.5
mid=(y[:,20:30]-x[:,20:30]).sum(1)*.5
late=(y[:,42:46]-x[:,42:46]).sum(1)*.5
np.testing.assert_allclose(mid,removed*.5,atol=1e-10)
np.testing.assert_allclose(late,removed*.5,atol=1e-10)
np.testing.assert_allclose(removed.sum(),s['default_all_days']['total_displaced_mwh'])
assert (x[:,32:42]-y[:,32:42]<=np.maximum(x[:,32:42],0)+1e-10).all()
assert (y[:,32:42]<=x[:,32:42]+1e-10).all()
cap=pd.read_csv(p/'scenario_capacity.csv').set_index('substation').iloc[:,0]
limits=before.index.get_level_values('site').map(cap).to_numpy()
for idx in [list(range(20,30)),list(range(42,46))]:
    assert (y[:,idx]<=np.maximum(x[:,idx],limits[:,None])+1e-10).all()
untouched=list(range(20))+[30,31,46,47]
np.testing.assert_array_equal(x[:,untouched],y[:,untouched])
assert curves.exempt_multiplier.eq(1).all()
assert curves.loc[~curves.hh.between(32,41),'nonexempt_multiplier'].eq(1).all()
sweep=pd.read_csv(p/'sensitivity.csv')
assert len(sweep)==96 and sweep.max_energy_error_mwh.max()<1e-8
assert sweep.loc[sweep.response_rate==0,'total_displaced_mwh'].eq(0).all()
# Verify dashboard API on first complete day and first actively shifted day.
examples=[]
for i in dict.fromkeys([0,int(np.flatnonzero(removed>1e-8)[0])]):
    site,date=before.index[i]
    out=replay_scenario(day4,p,site,str(date.date()))
    np.testing.assert_allclose(out['intervals'].simulated_signed_mw,y[i],atol=1e-10)
    examples.append({'site':site,'date':str(date.date()),'moved_mwh':out['metrics']['total_displaced_mwh']})
report=dict(passed=True,complete_site_days=len(x),sweep_cases=96,sweep_site_day_runs=s['sweep_site_day_runs'],
            independent_max_energy_error_mwh=float(abs(energy_error).max()),examples=examples,
            checks=['input hashes','chronological calibration','Brier and confusion counts','source signed flows',
                    'MW to MWh conservation','equal destination energy','positive-import removal bound',
                    'destination headroom','unaffected intervals','exempt price','zero-response sweep','replay API'],
            artifact_hashes={f.name:digest(f) for f in p.iterdir() if f.suffix in ['.csv','.json','.parquet'] and f.name!='audit.json'})
(p/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
