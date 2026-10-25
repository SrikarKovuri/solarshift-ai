"""Validation-only warnings, chronological calibration and constrained scenarios."""
import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from .pipeline import digest
from .response import Scenario, prob_exceed, price_multiplier, simulate, EVENING, MIDDAY, LATE

CAL_END = pd.Timestamp('2023-11-01')


def daily_table(v, thresholds):
    if not v.date.between('2023-05-01','2024-04-30').all() or not v.split.eq('val').all():
        raise ValueError('Only validation data allowed')
    if v.duplicated(['site','date','hh']).any() or not v.hh.isin(range(48)).all():
        raise ValueError('Invalid interval keys')
    cols = ['actual_magnitude_mw','q10_mw','q50_mw','q90_mw','weekly_mw','yesterday_mw']
    if not np.isfinite(v[cols]).all().all():
        raise ValueError('Nonfinite forecast or actual')
    e = v[v.hh.between(32,41)]
    d = e.groupby(['site','date'])[cols].mean()
    d['n'] = e.groupby(['site','date']).size()
    d = d[d.n == 10].reset_index()
    d['threshold_mw'] = d.site.map(thresholds)
    if d.threshold_mw.isna().any():
        raise ValueError('Missing training threshold')
    d['event'] = d.actual_magnitude_mw > d.threshold_mw
    d['p_raw'] = prob_exceed(d[['q10_mw','q50_mw','q90_mw']], d.threshold_mw)
    return d


def fit_calibration(d):
    early = d[d.date < CAL_END]
    if len(early) == 0 or early.event.nunique() < 2:
        raise ValueError('Both event classes required in early validation')
    iso = IsotonicRegression(y_min=0,y_max=1,out_of_bounds='clip')
    iso.fit(early.p_raw, early.event.astype(int))
    return {'x':iso.X_thresholds_.tolist(), 'y':iso.y_thresholds_.tolist(),
            'fit_start':str(early.date.min().date()), 'fit_end':str(early.date.max().date()),
            'fit_rows':len(early), 'evaluation_start':'2023-11-01',
            'method':'pooled isotonic; linear interpolation; clipped endpoints'}


def score(event, signal):
    e,s = np.asarray(event,bool),np.asarray(signal,bool)
    tp,fp,fn,tn = [int(z.sum()) for z in (e&s,~e&s,e&~s,~e&~s)]
    precision = tp/(tp+fp) if tp+fp else 0.
    recall = tp/(tp+fn) if tp+fn else 0.
    return dict(n=len(e),tp=tp,fp=fp,fn=fn,tn=tn,precision=precision,recall=recall,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
                warning_frequency=float(s.mean()),false_alarm_fraction_of_warnings=fp/(tp+fp) if tp+fp else None,
                false_alarms_per_30_eligible_site_days=30*fp/len(e))


def scenario_metrics(x,y,info):
    def reduction(before,after):
        b=float(before.mean())
        return float(100*(b-after.mean())/b) if b>0 else None
    return dict(mean_displaced_mwh=float(info['moved_mwh'].mean()),
                total_displaced_mwh=float(info['moved_mwh'].sum()),
                capacity_limited_days=int(info['capacity_limited'].sum()),
                max_energy_error_mwh=float(abs(info['energy_error_mwh']).max()),
                evening_mean_reduction_pct=reduction(x[:,EVENING],y[:,EVENING]),
                evening_max_reduction_pct=reduction(x[:,EVENING].max(1),y[:,EVENING].max(1)),
                whole_day_max_reduction_pct=reduction(x.max(1),y.max(1)),
                whole_day_absolute_flow_max_change_mw=float((abs(y).max(1)-abs(x).max(1)).mean()),
                increased_whole_day_max_days=int((y.max(1)>x.max(1)+1e-9).sum()),
                late_window_peak_increased_days=int((y[:,LATE].max(1)>x[:,LATE].max(1)+1e-9).sum()),
                new_peak_outside_evening_days=int((~np.isin(y.argmax(1),EVENING)&np.isin(x.argmax(1),EVENING)).sum()))


def check_scenario(x,y,info,cap):
    assert abs(info['energy_error_mwh']).max() < 1e-8
    assert (x[:,EVENING]-y[:,EVENING] <= np.maximum(x[:,EVENING],0)+1e-9).all()
    assert (y[:,EVENING] <= x[:,EVENING]+1e-9).all()
    for idx in [MIDDAY,LATE]:
        assert (y[:,idx] >= x[:,idx]-1e-9).all()
        assert (y[:,idx] <= np.maximum(cap[:,None],x[:,idx])+1e-9).all()


def run(source,output):
    output.mkdir(parents=True,exist_ok=True)
    # Validate Day 4 artifacts before relying on them.
    audit = json.loads((source/'audit.json').read_text())
    required = ['validation_forecasts.parquet','clean_development.parquet','peak_thresholds_training.csv']
    hashes = {n:digest(source/n) for n in required}
    for n,h in hashes.items():
        if audit['artifact_hashes'].get(n) != h:
            raise ValueError(f'Day 4 artifact hash mismatch: {n}')
    cols = ['site','date','hh','split','signed_actual_mw','actual_magnitude_mw','q10_mw','q50_mw','q90_mw','weekly_mw','yesterday_mw']
    v = pd.read_parquet(source/'validation_forecasts.parquet',columns=cols)
    thresholds = pd.read_csv(source/'peak_thresholds_training.csv').set_index('substation').iloc[:,0]
    # Independently reconstruct fixed thresholds and scenario ceiling from training only.
    tr = pd.read_parquet(source/'clean_development.parquet',columns=['substation','date','hh','mw'],filters=[('date','>=',pd.Timestamp('2021-05-01')),('date','<',pd.Timestamp('2023-05-01'))])
    te = tr[tr.hh.between(32,41)].groupby(['substation','date']).mw.agg(['mean','count'])
    independent = te[te['count']==10].groupby('substation')['mean'].quantile(.9)
    np.testing.assert_allclose(thresholds,independent.reindex(thresholds.index),atol=1e-6)
    capacity = tr.groupby('substation').mw.quantile(.99).reindex(thresholds.index)
    capacity.rename('assumed_import_ceiling_mw').to_csv(output/'scenario_capacity.csv')
    del tr,te
    d = daily_table(v,thresholds)
    cal = fit_calibration(d)
    (output/'calibration.json').write_text(json.dumps(cal,indent=2))
    d['period'] = np.where(d.date<CAL_END,'calibration_fit','later_validation')
    d['p_calibrated'] = np.where(d.date>=CAL_END,np.interp(d.p_raw,cal['x'],cal['y']),np.nan)
    d['multiplier'] = price_multiplier(d.p_calibrated.fillna(0))
    d.loc[d.date<CAL_END,'multiplier'] = np.nan
    d.to_csv(output/'daily_warnings.csv',index=False)
    later = d[d.date>=CAL_END].copy()
    rules = {'raw_probability_0.30':later.p_raw>=.3,'calibrated_probability_0.30':later.p_calibrated>=.3,
             'weekly_threshold':later.weekly_mw>later.threshold_mw,'yesterday_threshold':later.yesterday_mw>later.threshold_mw,
             'seasonal_weekdays':later.date.dt.month.isin([12,1,2,6,7,8]) & (later.date.dt.dayofweek<5),
             'always_warn':np.ones(len(later),bool),'never_warn':np.zeros(len(later),bool)}
    pd.DataFrame([dict(rule=n,**score(later.event,s)) for n,s in rules.items()]).to_csv(output/'warning_metrics.csv',index=False)
    reliability=[]
    briers={}
    for col in ['p_raw','p_calibrated']:
        briers[col]=float(np.mean((later[col]-later.event.astype(int))**2))
        bins=np.minimum((later[col]*10).astype(int),9)
        for k in range(10):
            b=later[bins==k]
            reliability.append(dict(model=col,bin_lower=k/10,bin_upper=(k+1)/10,n=len(b),mean_probability=b[col].mean(),event_rate=b.event.mean()))
    pd.DataFrame(reliability).to_csv(output/'reliability.csv',index=False)
    loads=v[v.date>=CAL_END].pivot(index=['site','date'],columns='hh',values='signed_actual_mw').reindex(columns=range(48)).dropna()
    keys=later.set_index(['site','date']).reindex(loads.index)
    if keys.multiplier.isna().any():
        raise ValueError('Complete-day simulation missing warning')
    x=loads.to_numpy(); m=keys.multiplier.to_numpy(); cap=loads.index.get_level_values('site').map(capacity).to_numpy()
    params=Scenario()
    y,info=simulate(x,m,cap,params)
    check_scenario(x,y,info,cap)
    base=loads.index.to_frame(index=False)
    base['event']=keys.event.to_numpy(); base['multiplier']=m
    for name,val in info.items(): base[name]=val
    for name,arr in [('before',x),('after',y)]:
        base[f'energy_{name}_mwh']=arr.sum(1)*.5
        base[f'evening_mean_{name}_mw']=arr[:,EVENING].mean(1)
        base[f'evening_max_{name}_mw']=arr[:,EVENING].max(1)
        base[f'day_max_{name}_mw']=arr.max(1)
    base.to_csv(output/'default_scenarios.csv',index=False)
    # Full curves for dashboard; default scenario only, editable API handles other choices.
    curves=pd.DataFrame({'site':np.repeat(base.site,48),'date':np.repeat(base.date,48),'hh':np.tile(np.arange(48),len(base)),
                         'before_signed_mw':x.ravel(),'after_signed_mw':y.ravel(),
                         'nonexempt_multiplier':np.where(np.tile(np.isin(np.arange(48),EVENING),len(base)),np.repeat(m,48),1.),
                         'exempt_multiplier':1.})
    curves.to_parquet(output/'default_curves.parquet',index=False)
    sweep=[]
    for cf in [.8,1.,1.2,1.5]:
        for r in [0,.05,.10,.15,.20,.30]:
            for f in [.05,.10,.15,.25]:
                after,di=simulate(x,m,cap*cf,replace(params,response_rate=r,flexible_fraction=f))
                check_scenario(x,after,di,cap*cf)
                sweep.append(dict(capacity_factor=cf,response_rate=r,flexible_fraction=f,**scenario_metrics(x,after,di)))
    pd.DataFrame(sweep).to_csv(output/'sensitivity.csv',index=False)
    summary=dict(status='later_validation_scenario_analysis',calibration_fit_days=cal['fit_rows'],evaluation_site_days=len(later),
                 complete_simulation_site_days=len(x),excluded_incomplete_simulation_days=len(later)-len(x),
                 defaults=asdict(params),capacity_assumption='site training 99th percentile magnitude; not equipment rating',
                 brier=briers,warning_frequency=float((later.p_calibrated>=.3).mean()),uplift_frequency=float((later.multiplier>1).mean()),
                 default_all_days=scenario_metrics(x,y,info),
                 default_signal_days=scenario_metrics(x[m>1],y[m>1],{k:z[m>1] for k,z in info.items()}) if (m>1).any() else None,
                 default_event_days=scenario_metrics(x[keys.event.to_numpy(bool)],y[keys.event.to_numpy(bool)],{k:z[keys.event.to_numpy(bool)] for k,z in info.items()}) if keys.event.any() else None,
                 baseline_days_above_assumed_ceiling=int((x.max(1)>cap).sum()),
                 sweep_scenarios=len(sweep),sweep_site_day_runs=len(x)*len(sweep),
                 input_hashes=hashes,reserved_test_scored=False,
                 implementation_hashes={p.name:digest(p) for p in [Path(__file__),Path(__file__).with_name('response.py')]})
    (output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('results/generated/substation_day4'))
    p.add_argument('--output',type=Path,default=Path('results/generated/substation_day5'))
    a=p.parse_args();run(a.source,a.output)
