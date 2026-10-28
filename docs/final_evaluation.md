# Final frozen evaluation

## Approval and freeze

Srikar explicitly confirmed in the project chat that the team approved the method
freeze and final test. The record attributes that confirmation to Srikar; it does
not invent individual signatures. `results/evidence/final_evaluation/freeze.json`
records the approval, UTC timestamp, model/data hashes, feature list, parameters,
calibration, response defaults and success thresholds before any test archive was
opened. An exclusive run marker prevents accidental second scoring in the same
output directory. A failed run requires documented investigation, not silent retries.

The selected 63-site cohort and three training-only models were retained unchanged.
Probability calibration remains fitted on May–October 2023. The CQR widening is
0.0203708 MW, also fitted on early validation. This intentionally differs from the
reference document's train+validation refit and whole-validation CQR: the user
approved freezing the current local implementation. No held-out tuning occurred.

## Executed test

The test covers 1 May 2024–29 April 2025: 972,371 eligible intervals, including
203,619 evening intervals. Fixed training spike scales and the existing flat-run
rules are applied to test data. Both DST-change dates are excluded. Magnitude is
the absolute value after averaging two signed quarter-hour observations. Lags use
past days on a complete calendar; test-day targets never enter same-day features.
Train-derived scaling/site attributes remain fixed. Cached genuine day-ahead
temperature is subject to the same historical availability assumptions as validation.

Final evening MAE improves 54.216% over weekly persistence. The paired calendar-week
bootstrap interval is 50.260–57.269% (500 draws, seed 2112, 53 blocks). Raw interval
coverage is 75.801%; fixed CQR coverage is 77.210%. The latter meets the frozen
70–90% tolerance but remains below nominal 80%, so no exact coverage guarantee is
claimed. Warning F1 exceeds both weekly-threshold and fixed-seasonal warning rules.
See metrics.csv, warning_metrics.csv, reliability.csv and slices.csv for full values.

The default response shifts a mean 0.047203 MWh per complete site-day; aggregate
mean evening reduction is 0.088561%. The whole-day maximum increases on 32 days.
These are retrospective scenarios with measured headroom, not causal household
response, measured energy savings or operational decisions. All 96 parameter
combinations conserve energy to numerical tolerance.

## Verification and robustness scope

`python scripts/verify_final.py` independently recomputes model/window errors,
coverage and headline improvement from the saved predictions, checks frozen hashes,
chronology, DST exclusions, signed/magnitude agreement, warning counts and scenario
energy conservation. This audit does not refit or score the raw test again.

The project includes monthly/day-type test slices, monthly/anomaly validation
slices, and a separate lockdown-excluded training sensitivity run. An instrumented
exact training repeat must match the saved validation quantile predictions. Carbon
is estimated for the repeat plus sensitivity, not retroactively assigned to the
original training run. See results/evidence/submission_robustness.

Earlier-year retraining and transfer to mixed/new substations are outside the final
frozen experiment. The delivered model does not claim those generalisation results.
Optional SHAP, LSTM, live operation and hosting are not needed to run or assess this
research prototype. Grouped permutation importance is global predictive sensitivity;
it does not establish a causal temperature direction or every explainability claim
in the original reference proposal.
