"""Frozen held-out evaluation. Explicit approval and an exclusive run marker required."""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from . import ausgrid
from .pipeline import FEATURES, PARAMS, _site_features, digest, metrics
from .evaluate import bootstrap
from .response import Scenario, prob_exceed, price_multiplier, simulate, EVENING
from .day5 import score, scenario_metrics, check_scenario

START=pd.Timestamp('2024-05-01')
END=pd.Timestamp('2025-04-29')


def frozen_files(root):
    d4=root/'substation_day4'
    files=[d4/n for n in ['q10.ubj','q50.ubj','q90.ubj','ridge.json','cohort.csv',
         'training_cleaning_scales.csv','peak_thresholds_training.csv','clean_development.parquet']]
    files += [root/'substation_day5'/n for n in ['calibration.json','scenario_capacity.csv']]
    files += [root/'substation_day7'/'evaluation.json']
    return files


def freeze(root, out, approval):
    if not approval.strip():raise ValueError('Human approval record required')
    out.mkdir(parents=True,exist_ok=True)
    record=dict(created_utc=datetime.now(timezone.utc).isoformat(),approval=approval,
        approval_source='User explicitly confirmed team approval in Codex chat; no individual signatures generated.',
        test_start=str(START.date()),test_end=str(END.date()),parameters=PARAMS,features=FEATURES,
        model_policy='Use existing training-only models unchanged; no train+validation refit.',
        calibration_policy='Keep May–October probability calibration and chronological CQR widening unchanged.',
        deviations_from_theo='63 training-selected sites; genuine temperature only; no future-error donors; training-only frozen models rather than train+validation refit; existing chronological CQR retained.',
        thresholds=dict(mae_improvement_pct=30,bootstrap_lower_pct=15,coverage_min=.7,coverage_max=.9),
        scenario=asdict(Scenario()),hashes={str(p.relative_to(root)):digest(p) for p in frozen_files(root)},
        implementation_hashes={p.name:digest(p) for p in Path(__file__).parent.glob('*.py')})
    with (out/'freeze.json').open('x') as f:json.dump(record,f,indent=2)
    return record


def clean_test(w, scales):
    """Apply the original within-day filters with frozen TRAINING spike scales."""
    w=w.sort_values(['substation','date']).reset_index(drop=True)
    if w.duplicated(['substation','date']).any() or not w.date.between(START,END).all():
        raise ValueError('Invalid held-out keys/dates')
    if not w.unit.str.upper().eq('MW').all():raise ValueError('Expected MW')
    x=w[list(range(96))].to_numpy(float)
    flags=np.where(np.isfinite(x),0,1).astype('uint8')
    sc=scales.set_index('substation').reindex(w.substation)
    if sc[['change_median','change_scale']].isna().any().any():raise ValueError('Missing frozen scale')
    d=np.diff(x,axis=1)
    z=abs(d-sc.change_median.to_numpy()[:,None])/sc.change_scale.to_numpy()[:,None]
    spike=(z[:,:-1]>15)&(z[:,1:]>15)&(np.sign(d[:,:-1])!=np.sign(d[:,1:]))
    flags[:,1:-1]|=spike.astype('uint8')*2
    run=np.zeros(len(w),dtype=int)
    for j in range(1,96):
        run=np.where(np.isfinite(x[:,j])&(x[:,j]==x[:,j-1]),run+1,0)
        flags[run>=15,j-15:j+1]|=4
    dst=w.date.isin(pd.to_datetime(['2024-10-06','2025-04-06'])).to_numpy()
    flags[dst]|=8;x[flags>0]=np.nan
    half=x.reshape(-1,48,2).mean(2)
    out=pd.DataFrame(dict(substation=np.repeat(w.substation.to_numpy(),48),
        date=np.repeat(w.date.to_numpy(),48),hh=np.tile(np.arange(48),len(w)),
        mw_published=half.ravel().astype('float32'),quality_flags=np.bitwise_or.reduce(flags.reshape(-1,48,2),axis=2).ravel()))
    out['mw']=out.mw_published.abs();out['sign_available']=True
    return out


def final_weather(path):
    w=pd.read_csv(io.StringIO(path.read_text().split('\n\n',1)[1]))
    w.columns=[c.split(' (')[0] for c in w.columns]
    w['valid_time']=pd.to_datetime(w.time)
    w=w[w.valid_time<END+pd.Timedelta(days=1)].copy()
    w['date']=w.valid_time.dt.normalize();w['hour']=w.valid_time.dt.hour
    w=w.drop_duplicates(['date','hour'],keep=False)
    w=w[['date','hour','temperature_2m_previous_day1']].rename(columns={'temperature_2m_previous_day1':'temp'})
    d=w.groupby('date').temp.agg(tmax='max',tmin='min',tmean='mean',count='count')
    d.loc[d['count']<24,['tmax','tmin','tmean']]=np.nan
    return w.merge(d.drop(columns='count'),on='date')


def assess(v, adjustment):
    rows=[]
    for window,mask in [('full_day',np.ones(len(v),bool)),('evening',v.hh.between(32,41))]:
        f=v.loc[mask];y=f.actual_magnitude_mw
        for name,col in [('weekly','weekly_mw'),('yesterday','yesterday_mw'),('weather_calendar','weather_calendar_mw'),('quantile_boosted','q50_mw')]:
            rows.append(dict(window=window,model=name,**metrics(y,f[col],f.level_mw)))
    e=v[v.hh.between(32,41)].copy(); y=e.actual_magnitude_mw
    band=dict(raw_coverage=float(y.between(e.q10_mw,e.q90_mw).mean()),
        cqr_coverage=float(y.between((e.q10_mw-adjustment).clip(lower=0),e.q90_mw+adjustment).mean()),
        raw_width_mw=float((e.q90_mw-e.q10_mw).mean()),
        cqr_width_mw=float((e.q90_mw+adjustment-(e.q10_mw-adjustment).clip(lower=0)).mean()))
    for q in (.1,.5,.9):
        err=y-e[f'q{int(q*100)}_mw'];band[f'pinball_q{int(q*100)}_mw']=float(np.maximum(q*err,(q-1)*err).mean())
    return pd.DataFrame(rows),band,bootstrap(e)


def run(root, source, out):
    frozen=json.loads((out/'freeze.json').read_text())
    for name,h in frozen['hashes'].items():
        if digest(root/name)!=h:raise ValueError(f'Frozen artifact changed: {name}')
    for name,h in frozen['implementation_hashes'].items():
        if digest(Path(__file__).parent/name)!=h:raise ValueError(f'Frozen implementation changed: {name}')
    # Reserve before any held-out data access. A failed run requires documented recovery.
    with (out/'run_started.json').open('x') as f:
        json.dump(dict(started_utc=datetime.now(timezone.utc).isoformat(),freeze_sha256=digest(out/'freeze.json')),f)
    d4=root/'substation_day4';d5=root/'substation_day5'
    sel=pd.read_csv(d4/'cohort.csv')
    archive=source/'data/raw/ausgrid/ausgrid_zss_FY2025.zip'
    print('Opening authorised FY2025 archive',flush=True)
    w=ausgrid.read_year_wide(archive);w['date']=pd.to_datetime(w.date)
    w['substation']=w.substation.map(ausgrid.canonical_name)
    w=w[w.substation.isin(sel.substation)&w.date.between(START,END)]
    test=clean_test(w,pd.read_csv(d4/'training_cleaning_scales.csv'))
    development=pd.read_parquet(d4/'clean_development.parquet')
    long=pd.concat([development[development.substation.isin(sel.substation)],test],ignore_index=True)
    wx={z:final_weather(source/'data/raw/weather'/f'openmeteo_{z}__gfs_dayahead.csv') for z in sel.weather_zone.unique()}
    frames=[];counts=[]
    for _,site in sel.iterrows():
        f=_site_features(long[long.substation==site.substation],site,wx[site.weather_zone],str(END.date()))
        f=f[f.date.between(START,END)].copy()
        ok=(np.isfinite(f[FEATURES+['y']]).all(axis=1)&f.interval_start.notna()&f.quality_flags.eq(0)&f.weather_latest_issue_time.lt(f.issue_time))
        counts.append(dict(site=site.substation,total=len(f),eligible=int(ok.sum())))
        frames.append(f[ok])
    v=pd.concat(frames,ignore_index=True)
    if v.empty:raise ValueError('No eligible test intervals')
    v['split']='test';v['site']=v.substation;v['signed_actual_mw']=v.mw_published
    print(f'Predicting {len(v):,} held-out intervals using frozen models',flush=True)
    raw=[]
    for q in (10,50,90):
        m=XGBRegressor();m.load_model(d4/f'q{q}.ubj');raw.append(m.predict(v[FEATURES]))
    raw=np.column_stack(raw);pred=np.sort(np.maximum(raw,0),axis=1)*v.level_mw.to_numpy()[:,None]
    for j,q in enumerate((10,50,90)):v[f'q{q}_mw']=pred[:,j]
    ridge=json.loads((d4/'ridge.json').read_text())
    v['weather_calendar_mw']=np.maximum(0,((v[ridge['features']].to_numpy()-ridge['mean'])/ridge['scale'])@ridge['coef']+ridge['intercept'])*v.level_mw
    v['weekly_mw']=v.lag_d7*v.level_mw;v['yesterday_mw']=v.lag_d1*v.level_mw
    adjustment=json.loads((root/'substation_day7/evaluation.json').read_text())['calibration']['adjustment_mw']
    comparisons,band,boot=assess(v,adjustment)
    comparisons.to_csv(out/'metrics.csv',index=False);pd.DataFrame(counts).to_csv(out/'eligibility.csv',index=False)
    slices=[]
    for group,keys in [('month',v.date.dt.strftime('%Y-%m')),('day_type',np.where((v.date.dt.dayofweek>=5)|v.holiday.eq(1),'weekend_or_holiday','weekday'))]:
        for key,f in v.groupby(keys):
            e=f[f.hh.between(32,41)];slices.append(dict(group=group,label=key,**metrics(e.actual_magnitude_mw,e.q50_mw,e.level_mw)))
    pd.DataFrame(slices).to_csv(out/'slices.csv',index=False)
    e=v[v.hh.between(32,41)]
    cols=['actual_magnitude_mw','q10_mw','q50_mw','q90_mw','weekly_mw','yesterday_mw']
    d=e.groupby(['site','date'])[cols].mean();d['n']=e.groupby(['site','date']).size();d=d[d.n==10].reset_index()
    thresholds=pd.read_csv(d4/'peak_thresholds_training.csv').set_index('substation').iloc[:,0]
    d['threshold_mw']=d.site.map(thresholds);d['event']=d.actual_magnitude_mw>d.threshold_mw
    d['p_raw']=prob_exceed(d[['q10_mw','q50_mw','q90_mw']],d.threshold_mw)
    cal=json.loads((d5/'calibration.json').read_text());d['p_calibrated']=np.interp(d.p_raw,cal['x'],cal['y']);d['multiplier']=price_multiplier(d.p_calibrated)
    rules={'calibrated_probability_0.30':d.p_calibrated>=.3,'weekly_threshold':d.weekly_mw>d.threshold_mw,
        'yesterday_threshold':d.yesterday_mw>d.threshold_mw,'seasonal_weekdays':d.date.dt.month.isin([12,1,2,6,7,8])&(d.date.dt.dayofweek<5)}
    warnings=pd.DataFrame([dict(rule=n,**score(d.event,s)) for n,s in rules.items()]);warnings.to_csv(out/'warning_metrics.csv',index=False)
    reliability=[]
    for key in ['p_raw','p_calibrated']:
        bins=np.minimum((d[key]*10).astype(int),9)
        for k,f in d.groupby(bins):reliability.append(dict(model=key,bin_lower=k/10,n=len(f),mean_probability=f[key].mean(),event_rate=f.event.mean()))
    pd.DataFrame(reliability).to_csv(out/'reliability.csv',index=False)
    loads=v.pivot(index=['site','date'],columns='hh',values='signed_actual_mw').reindex(columns=range(48)).dropna()
    keys=d.set_index(['site','date']).reindex(loads.index)
    capacity=pd.read_csv(d5/'scenario_capacity.csv').set_index('substation').iloc[:,0]
    x=loads.to_numpy();cap=loads.index.get_level_values('site').map(capacity).to_numpy();m=keys.multiplier.to_numpy()
    y,info=simulate(x,m,cap,Scenario());check_scenario(x,y,info,cap)
    sweep=[]
    for cf in [.8,1.,1.2,1.5]:
        for response in [0,.05,.10,.15,.20,.30]:
            for flexible in [.05,.10,.15,.25]:
                sy,si=simulate(x,m,cap*cf,replace(Scenario(),response_rate=response,flexible_fraction=flexible))
                check_scenario(x,sy,si,cap*cf)
                sweep.append(dict(capacity_factor=cf,response=response,flexible=flexible,**scenario_metrics(x,sy,si)))
    pd.DataFrame(sweep).to_csv(out/'sensitivity.csv',index=False)
    f1=warnings.set_index('rule').f1
    summary=dict(status='held_out_test_complete',test_start=str(v.date.min().date()),test_end=str(v.date.max().date()),
        rows=len(v),sites=v.site.nunique(),evening_rows=len(e),complete_simulation_days=len(x),
        bootstrap=boot,intervals=band,cqr_adjustment_mw=adjustment,
        probability_brier=float(np.mean((d.p_calibrated-d.event.astype(int))**2)),scenario=scenario_metrics(x,y,info),
        sensitivity_combinations=len(sweep),
        criteria=dict(mae_improvement_at_least_30pct=boot['improvement_pct']>=30,
            bootstrap_lower_above_15pct=boot['ci95_pct'][0]>15,cqr_coverage_70_to_90pct=.7<=band['cqr_coverage']<=.9,
            warning_f1_above_weekly_and_seasonal=bool(f1['calibrated_probability_0.30']>max(f1['weekly_threshold'],f1['seasonal_weekdays']))),
        archive_sha256=digest(archive),freeze_sha256=digest(out/'freeze.json'),
        weather_hashes={z:digest(source/'data/raw/weather'/f'openmeteo_{z}__gfs_dayahead.csv') for z in wx},
        limitations=['Historical availability assumptions remain unverified operationally.',
            'Scenario effects are simulated with known measured headroom, not causal or bill-saving estimates.',
            'Same sites across splits; not evidence of new-site generalisation.',
            'No model, rule or calibration changed after held-out data access.'])
    v.to_parquet(out/'test_forecasts.parquet',index=False)
    d.to_csv(out/'daily_warnings.csv',index=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--approval',required=True)
    a=p.parse_args();root=Path('results/generated');out=root/'final_evaluation'
    freeze(root,out,a.approval);run(root,a.source,out)
