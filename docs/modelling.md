# Supervised forecasting and validation

This document describes the archived household experiment. For the active
substation prototype, see [Day 4 integration](substation_day4.md).

## Model and forecast definition

One pooled XGBoost regression model predicts GC and another predicts GG across
the fixed 30-household cohort. Each input row represents one of the following
day's 48 half-hours. Slot/calendar features distinguish horizons; no recursive
prediction consumes actual target-day measurements. The explicit 17-feature
allowlist from the forecasting milestone remains unchanged. There is no fitted
scaler, household-ID encoding, weather proxy or hidden target-derived feature.

The intended downstream use is next-day pricing and response simulation. This
milestone supplies real model outputs; it does not establish pricing benefits.

XGBoost uses CPU histogram trees with squared-error loss, seed 2112 and four
threads. Squared-error training estimates conditional means; it does not directly
optimise the MAE selection objective. Both targets are clipped below zero in
selection, evaluation and inference. No capacity ceiling or fitted night-time rule
is applied. Tiny positive night-time PV forecasts remain possible.

## Bounded model selection

The configuration was fixed before observing the model results. Each target uses
three candidates: depth/trees (3/200), (5/300), (6/400), all with learning rate 0.05,
row subsampling 0.8, feature subsampling 0.9, minimum child weight 10 and L2
regularisation 10. Trees are not stopped using the final test set. Fixed iteration
counts bound this six-fit CPU search; no adaptive expansion followed the result.

All fits use July 2010–December 2011 training rows. Candidate selection uses
January–June 2012 validation: evening MAE for GC, full-day MAE for GG. Ties retain
the earlier, smaller candidate. The selected model is saved without a
train-plus-validation refit. Full-day and evening MAE/RMSE, per-household scores
and complete-cohort totals are then calculated on the exact baseline rows.

Validation has been reused for model selection, so the reported improvements are
optimistic development estimates, not unbiased final-test performance. The final
July 2012–June 2013 evaluation remains a later frozen-method task. Training and
evaluation load only the development feature files and reject test-labelled or
out-of-partition dates.

## Observed results and the 15% target

GC evening MAE decreases from 0.299297 to 0.255154 kWh per half-hour: 14.748692%.
This misses the proposal's 15% ambition by 0.251308 percentage points. The medium
and deeper candidates have evening MAE 0.257577 and 0.258830, respectively.
GG full-day MAE decreases from 0.074690 to 0.056677, or 24.116750%.
Its larger candidates give 0.056729 and 0.057084. Both selected the shallow model.

The narrow miss is reported without changing masks or trying many additional
configurations after inspecting the result. Larger models' worse validation
performance is consistent with limited benefit from additional complexity here,
but does not by itself prove overfitting. Unobserved occupancy/appliance behaviour,
absent archived weather forecasts, pooled household differences and the mean/MAE
objective mismatch are plausible limitations, not experimentally established causes.

No confidence intervals or causal benefits are claimed. Time dependence means
individual half-hours must not be treated as independent samples for uncertainty
estimation. A later robustness study can use blocked dates and predeclared methods.
The first supported cohort/date is used for illustrative charts, without ranking
forecast errors. Residual distributions include both tails in overflow bins.

## Model persistence and reproducibility

Native UBJSON files retain the trees and feature names. Separate JSON metadata
records feature order, target, preprocessing policy, seed, hyperparameters,
training/validation ranges, dependency versions and hashes. Saved configuration
and feature-manifest hashes bind evaluation to the original experiment.
Model reload checks permit at most 1e-6 kWh absolute float32 serialization
roundoff; actual selected-model reloads matched all real validation predictions
exactly. Reproducibility across other dependency versions or hardware is not assumed.

`scripts/verify_models.py` independently joins targets and weekly lags to processed
source measurements, uses the bare XGBoost Booster for inference, repeats both
selected fits, and recomputes metrics with NumPy. Existing data-source validation
and the baseline audit establish the chain back to original annual CSVs. Tests
use synthetic fixtures only and exercise leakage/date guards, tampering, wrong
targets, incomplete days, fair comparisons, selection, reloads and CLI output.

## Computational carbon estimate

CodeCarbon OfflineEmissionsTracker runs locally with country code AUS and API
submission disabled. Its forced CPU parameter is a TDP assumption: 15 W input
becomes 7.5 W effective power in CodeCarbon 3.0.7 constant mode (50% factor).
RAM is assumed 3 W. The tracker records duration, effective powers, estimated
energy and kg CO2e; the committed evidence contains these values and limitations.
The bundled country's mean intensity is not a current NSW marginal emissions
factor, nor a factor for the 2010–2013 household observations.

The scope is the six-fit search including its validation predictions, scoring and
serialization; it excludes dataset preparation, final report generation, audits,
repeat fits, development and AI assistance. It is an indicative assumption-based
estimate, not metered energy or the whole project's environmental footprint.
If CodeCarbon fails, the output explicitly records unavailable status and the
error; it never substitutes zero emissions. No administrator power sampling is used.

## Software references

- [XGBoost model persistence](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html)
- [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html)
- [CodeCarbon methodology](https://mlco2.github.io/codecarbon/methodology.html)
- [CodeCarbon parameters](https://mlco2.github.io/codecarbon/parameters.html)

Installed XGBoost 3.0.5 and CodeCarbon 3.0.7 source/API behaviour was also checked
locally; the lockfile records the environment used for the evidence.
