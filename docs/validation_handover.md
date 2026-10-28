# Historical validation handover

Superseded for submission status by [final evaluation](final_evaluation.md) and
[marker guide](marker_guide.md). Validation numbers below are unchanged; the later
final test, carbon repeat and Apple-inspired UI are now complete.

# Validation handover — 28 October 2026

The prototype now uses the ENG2112 Study Atlas palette, typography, sidebar treatment,
metric cards and chart styling. Forecast, response and evidence interactions retain
the existing units and provenance. The raw forecast band remains raw; the separate
CQR diagnostic is clearly labelled in Evidence & explanations.

## Executed findings

On 79,903 eligible evening intervals from November 2023–April 2024, model MAE is
1.102168 MW versus 2.181531 MW for weekly persistence: a 49.48% improvement.
A paired calendar-week bootstrap across all sites (25 blocks, 500 draws, seed 2112)
gives a percentile 95% interval of 42.82–55.11%. Boundary weeks remain partial.
This measures time variation for the observed sites, not generalisation to new sites.

Widen-only pooled CQR fitted on 97,633 May–October evening intervals adds 0.020371 MW
to each outer bound, clipping the lower bound at zero. The finite-sample order
statistic uses ceil((n+1)*0.8). Later coverage rises from 74.67% to 76.06%; mean width
rises from 3.012153 to 3.052894 MW. This remains below nominal 80% coverage.
Time dependence, distribution shift and pooled MW calibration prevent a coverage
guarantee. These results meet the proposed 70–90% tolerance, not proof of nominal
calibration. No model or probability rule was retuned using later-validation outcomes.

Monthly and anomaly-exclusion diagnostics are saved in `robustness.csv`. They are
sensitivity slices, not earlier-year retraining or a lockdown backtest. The source
forecast SHA-256 is checked against the existing audit before evaluation.

## Reproduce and demonstrate

From the solarshift-ai directory:

```sh
PYTHONPATH=src .venv/bin/python -m solarshift.substation.evaluate
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m streamlit run streamlit_app.py --server.address=127.0.0.1 --browser.gatherUsageStats=false
```

Requires the existing local Day 4–6 generated artifacts; see dashboard.md for
rebuilding inputs. Compact outputs are in results/evidence/substation_day7.
Use Aberdeen 66_11kV, 2023-11-12: inspect the forecast and warning, set response to
zero and restore it, set exemptions to 100%, then inspect the evaluation panel.
Download the CSV and assumptions to explain energy conservation and rebound.

## Review candidate and outstanding work

The saved model, feature definitions, training-selected cohort, probability mapping,
30% warning threshold, 1.5× price cap and response assumptions remain as documented
in the Day 4–6 artifacts. The CQR method above is a review candidate, not a claim of
team agreement. Proposed success criteria remain unapproved.

Genuine team method sign-off and reserved-year evaluation are outstanding. No
reserved observations were loaded or scored. Original substation-training carbon
was not instrumented; it cannot be reconstructed or replaced by the household
estimate. An instrumented repeat training run, broader earlier-year/mixed-cohort
robustness and external source/permission verification remain separate work.
No operational savings, causal effects or independent team approval are claimed.

Codex implemented the styling and validation diagnostics at Srikar's request.
Theo's supplied assets and prior local pipeline remain the source of the forecasts.
