"""Chronological validation diagnostics; never loads reserved observations."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .pipeline import digest


def validate(frame):
    if not frame.split.eq('val').all() or not frame.date.between('2023-05-01', '2024-04-30').all():
        raise ValueError('Only development validation observations allowed')
    cols = ['actual_magnitude_mw','q10_mw','q50_mw','q90_mw','weekly_mw']
    if frame.empty or not np.isfinite(frame[cols]).all().all():
        raise ValueError('Empty or nonfinite evaluation data')
    if frame.duplicated(['site','date','hh']).any():
        raise ValueError('Duplicate interval keys')


def cqr_adjustment(early, alpha=.2):
    scores = np.maximum(early.q10_mw-early.actual_magnitude_mw,
                        early.actual_magnitude_mw-early.q90_mw).to_numpy()
    if not len(scores):
        raise ValueError('Calibration observations required')
    rank = min(len(scores), int(np.ceil((len(scores)+1)*(1-alpha))))
    # Widen-only CQR avoids inverted bounds; conservative relative to signed scores.
    return max(0., float(np.partition(scores, rank-1)[rank-1]))


def metrics(f, adjustment):
    y=f.actual_magnitude_mw
    error=f.q50_mw-y
    lo=(f.q10_mw-adjustment).clip(lower=0)
    hi=f.q90_mw+adjustment
    return dict(rows=len(f),mae_mw=float(abs(error).mean()),rmse_mw=float(np.sqrt((error**2).mean())),
                nmae_pct=float(100*abs(error).mean()/y.mean()),
                weekly_mae_mw=float(abs(f.weekly_mw-y).mean()),
                raw_coverage=float(y.between(f.q10_mw,f.q90_mw).mean()),
                cqr_coverage=float(y.between(lo,hi).mean()),
                raw_width_mw=float((f.q90_mw-f.q10_mw).mean()),cqr_width_mw=float((hi-lo).mean()))


def bootstrap(f, repeats=500):
    # Resample entire calendar weeks jointly across sites, retaining within-week dependence.
    x=pd.DataFrame({'week':f.date.dt.to_period('W-SUN').astype(str),
                    'model':abs(f.q50_mw-f.actual_magnitude_mw),
                    'weekly':abs(f.weekly_mw-f.actual_magnitude_mw)})
    blocks=x.groupby('week')[['model','weekly']].sum().to_numpy()
    if len(blocks)<2 or blocks[:,1].sum()<=0:
        raise ValueError('At least two weeks and positive baseline error required')
    rng=np.random.default_rng(2112)
    sums=blocks[rng.integers(0,len(blocks),size=(repeats,len(blocks)))].sum(axis=1)
    improvements=100*(1-sums[:,0]/sums[:,1])
    return dict(improvement_pct=float(100*(1-blocks[:,0].sum()/blocks[:,1].sum())),
                ci95_pct=np.quantile(improvements,[.025,.975]).tolist(),blocks=len(blocks),
                resamples=repeats,seed=2112,method='paired calendar-week blocks across all sites; percentile interval')


def run(root):
    source=root/'substation_day4'/'validation_forecasts.parquet'
    audit=json.loads((root/'substation_day4'/'audit.json').read_text())
    source_hash=digest(source)
    if audit['artifact_hashes']['validation_forecasts.parquet']!=source_hash:
        raise ValueError('Validation artifact hash mismatch')
    f=pd.read_parquet(source)
    validate(f)
    e=f[f.hh.between(32,41)].copy()
    early=e[e.date<'2023-11-01']; later=e[e.date>='2023-11-01']
    if later.empty:
        raise ValueError('Later validation required')
    adjustment=cqr_adjustment(early)
    m=metrics(later,adjustment); boot=bootstrap(later)
    out=root/'substation_day7';out.mkdir(exist_ok=True)
    robustness=[]
    for label,part in [('all_later_validation',later),('excluding_anomaly_days',later[~later.anomaly.astype(bool)])]:
        if len(part):robustness.append(dict(subset=label,**metrics(part,adjustment)))
    for month,part in later.groupby(later.date.dt.strftime('%Y-%m')):
        robustness.append(dict(subset=month,**metrics(part,adjustment)))
    pd.DataFrame(robustness).to_csv(out/'robustness.csv',index=False)
    result=dict(status='validation_only',reserved_test_opened=False,source_sha256=source_hash,
                calibration=dict(start=str(early.date.min().date()),end=str(early.date.max().date()),rows=len(early),
                                 adjustment_mw=adjustment,method='pooled evening MW, widen-only CQR, nominal 80%'),
                evaluation=dict(start=str(later.date.min().date()),end=str(later.date.max().date()),**m),bootstrap=boot,
                proposed_criteria=dict(mae_improvement_at_least_30pct=boot['improvement_pct']>=30,
                                       improvement_lower_bound_above_15pct=boot['ci95_pct'][0]>15,
                                       cqr_coverage_70_to_90pct=.7<=m['cqr_coverage']<=.9),
                limitations=['Temporal dependence and distribution shift preclude an exchangeable CQR guarantee.',
                             'Pooled MW adjustment is not site-conditional coverage.',
                             'Partial boundary weeks retained; bootstrap reflects time variation, not new-site generalisation.',
                             'Anomaly exclusion and monthly slices are descriptive sensitivity checks, not earlier-year retraining.',
                             'Original substation training carbon was not instrumented and cannot be reconstructed.',
                             'Methods are a review candidate; genuine team sign-off and reserved test remain pending.'])
    (out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    run(Path('results/generated'))
