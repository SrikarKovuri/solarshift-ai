"""Development-only repeat training/carbon and lockdown exclusion sensitivity."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from .pipeline import FEATURES, PARAMS, eligible_rows, metrics, digest
from ..models.tracking import training_carbon


def run(root):
    d4=root/'substation_day4'; out=root/'submission_robustness';out.mkdir(exist_ok=True)
    f=pd.read_parquet(d4/'features_development.parquet')
    eligible=eligible_rows(f)
    tr=f[eligible & f.split.eq('train') & ~f.anomaly]
    va=f[eligible & f.split.eq('val')].copy()
    saved=pd.read_parquet(d4/'validation_forecasts.parquet')
    assert list(zip(va.substation,va.date,va.hh))==list(zip(saved.site,saved.date,saved.hh))
    rows=[]
    with training_carbon(out, dict(country_iso_code='AUS',cpu_power_w=15,ram_power_w=3)) as carbon:
        for label,t in [('repeat_original',tr),('exclude_2021_lockdown',tr[~tr.date.between('2021-06-26','2021-10-11')])]:
            raw=[]
            for q in (.1,.5,.9):
                print(f'{label} q={q}, {len(t):,} training intervals',flush=True)
                model=XGBRegressor(objective='reg:quantileerror',quantile_alpha=q,**PARAMS)
                model.fit(t[FEATURES],t.y)
                raw.append(model.predict(va[FEATURES]))
            pred=np.sort(np.maximum(np.column_stack(raw),0),axis=1)*va.level_mw.to_numpy()[:,None]
            if label=='repeat_original':
                np.testing.assert_allclose(pred,saved[['q10_mw','q50_mw','q90_mw']],rtol=0,atol=1e-6)
            for window,mask in [('full_day',np.ones(len(va),bool)),('evening',va.hh.between(32,41))]:
                rows.append(dict(experiment=label,window=window,train_rows=len(t),
                                 **metrics(va.loc[mask,'actual_magnitude_mw'],pred[mask,1],va.loc[mask,'level_mw'])))
    carbon['scope']='Six quantile fits: exact training repeat and lockdown-excluded sensitivity, plus validation prediction/checks; excludes original historical training, data preparation, final test, development and AI assistance.'
    (out/'carbon.json').write_text(json.dumps(carbon,indent=2)+'\n')
    pd.DataFrame(rows).to_csv(out/'metrics.csv',index=False)
    (out/'audit.json').write_text(json.dumps(dict(repeat_matches_original=True,reserved_test_opened=False,
        features_sha256=digest(d4/'features_development.parquet'),parameters=PARAMS,
        limitation='Lockdown exclusion retains the original training-selected cohort, training scaling and anomaly flags. It isolates training-row sensitivity, not an independent earlier-year or mixed-cohort backtest.'),indent=2)+'\n')
    print('Robustness and carbon complete',flush=True)

if __name__=='__main__':run(Path('results/generated'))
