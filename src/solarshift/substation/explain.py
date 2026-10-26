"""Reproducible grouped permutation diagnostics on later validation only."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from .pipeline import FEATURES, GROUPS, eligible_rows, digest


def run(source, output, sample_size=12000, repeats=5):
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(source/'features_development.parquet',
                            filters=[('date', '>=', pd.Timestamp('2023-11-01')),
                                     ('date', '<', pd.Timestamp('2024-05-01'))])
    frame = frame[eligible_rows(frame) & frame.split.eq('val') & frame.hh.between(32,41)]
    frame = frame.sample(n=min(sample_size,len(frame)), random_state=2112).reset_index(drop=True)
    if frame.empty:
        raise ValueError('No eligible explanation rows')
    models = []
    for q in (10,50,90):
        model = XGBRegressor(n_jobs=4)
        model.load_model(source/f'q{q}.ubj')
        models.append(model)
    x = frame[FEATURES].copy()
    def predict(values):
        raw = np.column_stack([m.predict(values) for m in models])
        return np.sort(np.maximum(raw,0), axis=1)[:,1]*frame.level_mw.to_numpy()
    actual = frame.actual_magnitude_mw.to_numpy()
    base = float(np.mean(abs(actual-predict(x))))
    rng = np.random.default_rng(2112)
    rows = []
    for name, cols in GROUPS.items():
        errors = []
        for _ in range(repeats):
            shuffled = x.copy()
            shuffled[cols] = x[cols].iloc[rng.permutation(len(x))].to_numpy()
            errors.append(float(np.mean(abs(actual-predict(shuffled)))-base))
        rows.append(dict(group=name,mae_increase_mw=float(np.mean(errors)),
                         repeat_sd_mw=float(np.std(errors,ddof=1)),repeats=repeats))
    result = pd.DataFrame(rows).sort_values('mae_increase_mw',ascending=False)
    result.to_csv(output/'importance.csv',index=False)
    summary = dict(status='later_validation_only',seed=2112,rows=len(frame),repeats=repeats,
                   sample_evening_mae_mw=base,first_date=str(frame.date.min()),last_date=str(frame.date.max()),
                   model_hashes={f'q{q}.ubj':digest(source/f'q{q}.ubj') for q in (10,50,90)},
                   feature_artifact_sha256=digest(source/'features_development.parquet'),
                   method='Joint row permutation per feature family; sorted/clipped quantile median; fixed original site MW scale.',
                   limitations='Global associations, not causal or selected-day explanations. Correlation and off-manifold shuffles affect importance. Repeat SD is not a confidence interval.',
                   shap='Deferred: grouped importance is the implemented explanation; no local SHAP claim.',
                   reserved_test_opened=False)
    (output/'explanations.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(result.to_string(index=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('results/generated/substation_day4'))
    parser.add_argument('--output',type=Path,default=Path('results/generated/substation_day6'))
    args=parser.parse_args()
    run(args.source,args.output)
