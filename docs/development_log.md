# Development log

## Data ingestion and validation — 21–22 October 2026 (Australia/Sydney)

Work began after explicit user approval on 21 October and continued on 22 October. Source acquisition and initial test
timestamps reflect the actual earlier execution; no timestamps or commits are backdated.

### Delivered

- Separate Python package and Git repository; the pre-existing study website was untouched.
- Complete archive validation and original annual CSV ingestion with provenance hashes.
- Conservative validation, explicit exclusion ledger, missing primary-channel coverage.
- Three interval Parquet files, daily summaries and household metadata.
- Offline interactive Plotly historical chart with channel toggles and zoom.
- Pinned dependencies, setup instructions, methodology and AI-assistance disclosure.
- Public repository: https://github.com/SrikarKovuri/solarshift-ai

### Executed data evidence

| Source year | Input channel-days | Accepted channel-days | Excluded channel-days | Accepted intervals |
|---|---:|---:|---:|---:|
| 2010–2011 | 269,735 | 268,257 | 1,478 | 12,876,336 |
| 2011–2012 | 270,304 | 268,727 | 1,577 | 12,898,896 |
| 2012–2013 | 268,557 | 266,651 | 1,906 | 12,799,248 |
| Total | 808,596 | 803,635 | 4,961 | 38,574,480 |

All 300 households appear in the accepted data. Counts include GC, GG and CL;
they are channel readings, not 38 million distinct household-time points.
4,268 expected GC/GG channel-days are unavailable after validation, including
missing source days and excluded records. No target values were imputed.

The primary exclusions were DST transition days and non-actual/unknown quality.
Reasons can overlap, so their counts need not sum to distinct excluded days.
High PV readings were flagged for investigation without automatically deleting them.

### Verification

- 29 Pytest cases cover acquisition failures, CSV variants, literal quality flags,
  invalid readings, duplicates, metadata conflicts, DST, midnight, energy units,
  missing CL and end-to-end chart generation. Final summary: `results/evidence/tests.json`.
- Independent standard-library CSV summation matched Parquet energy totals for
  each annual file/channel; physical invariants checked all 38,574,480 accepted readings.
  Evidence: `results/evidence/real_data_audit.json`.
- Complete ZIP CRC and file hashes: `results/evidence/acquisition.json`.
- Actual parser decisions and versions: `results/evidence/quality_report.json`.
- Historical chart inspected in a browser; power and daily energy were visibly plotted.
- Installed dependency consistency checked with `python -m pip check`.

The first test run had two incorrect expectations about cross-row metadata
inconsistency. Tests were corrected to isolate invalid-value checks; the separate
metadata-conflict test retains the conservative rejection expectation.
Editable installation hooks did not load reliably in the execution sandbox;
the documented setup uses a regular package installation, which was verified.

### Stage boundary and next work

At this checkpoint, forecasting had not started. The next increment was forecast
availability, leakage-safe features, chronological splitting and seasonal persistence. DST lag dependencies, licence
corroboration and the dataset's historical sampling limitations remain explicit.
No forecast performance, simulated savings or trained models are claimed.

Commit purpose: `feat(data): establish Ausgrid ingestion and validation pipeline`.
Human team review is pending; planned ownership is not claimed as completed contribution.


## Forecast-ready features and persistence benchmark — 22 October 2026

The user authorised the next functional increment and requested descriptive
milestone names rather than numbered-day labels. This log records the actual
working date; it does not imply work occurred on an additional calendar day.

### Implemented

- An 18:00 previous-day cutoff and 30-minute observation-availability allowance.
- Two-day and seven-day calendar lags, past-only rolling means, eligible previous-day
  readings with an explicit fallback indicator, and cyclical calendar features.
- Per-feature availability timestamps and executable leakage assertions.
- Training-only cohort selection (30 of the training-eligible households; seed 2112).
- Chronological partition definitions and development-only dataset generation.
- Weekly persistence predictions, full-day/evening MAE and RMSE, household scores,
  fixed-cohort aggregate errors, coverage reports and an offline interactive report.

### Executed evidence

1,488,960 training rows and 501,120 validation rows across two targets. Final-test
observations are excluded from the builder's source-file selection and evaluation.
Each selected household/target has 174 eligible validation days out of 182.
2,160 observed channel-days across development are rejected for incomplete targets
or required history; already-excluded target days are additionally absent upstream.

Validation demand MAE is 0.189325 kWh per half-hour overall and 0.299297 in the
16:00–21:00 window. PV MAE is 0.074690 overall and 0.034519 in that window.
Complete metrics and weighting are in `results/evidence/baseline_summary.json`.
No XGBoost improvement or physical/financial benefit has been measured.

The independent audit joins every validation target and prediction back to dated
source intervals, independently recomputes pooled MAE/RMSE, and checks feature
availability across every accepted training/validation row. Tests cover future-data
perturbation invariance, exact cutoff boundaries, missing-day/DST lag handling,
partition boundaries, cohort-selection independence, metrics and fixed-cohort sums.
Final executed test counts are in `results/evidence/forecast_tests.json`.

### Completion verification

After resuming the interrupted increment, all 51 tests passed again and the
baseline evaluation reproduced the recorded metrics. The independent source-join
audit passed for all 501,120 predictions and 1,990,080 feature rows. Dependency
consistency also passed. The regenerated report was inspected in the browser;
the chart now scrolls horizontally in narrow windows to avoid overlapping axes
and subplot titles.

The usable outputs at this milestone are command-line data/forecast pipelines
and offline interactive reports. The intended final group-project deliverable
remains an integrated local application with household/date selection, trained
forecasts, pricing controls and response simulation. That application is not
yet complete; the remaining work follows the agreed staged plan.

### Next increment

Train and validate separate demand/PV XGBoost models on this fixed benchmark,
with reproducible persistence and training-carbon instrumentation. This work has
not begun. Human team review remains pending; AI assistance is recorded separately.
