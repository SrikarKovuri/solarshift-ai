# Development log

## Warnings and constrained scenarios — 25 October 2026

Implemented at the user's request with Codex assistance using Theo's trigger and
simulation concepts. Preserved training-derived thresholds and model artifacts; fitted pooled
isotonic calibration only on early validation and evaluated later validation.
Implemented bounded signed-flow shifting, disjoint household groups, exemptions,
editable capacity/weights, conservation checks and the dashboard replay API. Executed
96 sensitivity scenarios on 6,569 complete days; 92 tests and independent artifact
audit passed. Results, assumptions, rebound risks and reproducibility are documented
in `substation_response.md`. No reserved test, external publication or team sign-off.


## Substation integration — 24 October 2026

At the user's request, Codex adapted Theo's source utilities and implemented the
substation pipeline, tests, validation replay interface and independent audit.
Training-only coverage and clustering replace imported test-conditioned selection;
genuine temperature-only weather replaces synthetic future-error donors. The
training-selected residential cohort has 63 sites. Full details, executed metrics
and reproducibility commands are in `substation_forecasting.md` and the generated outputs.
No team signatures, final-test results or new human-authorship claims were made.
Removed the redundant standalone `ai_assistance_log.md` and repaired its README
link at the user's request; retained factual attribution and development history.


## Source access and integration plan confirmed — 23 October 2026

The user provided the local `ENGG2112_ClosingThePeak` folder and requested
integration of Theo's requirements. Codex inspected the source inventory,
handoff/status documents, pre-registration, config, trigger, simulation and weather
donor logic. Updated `remaining_work_plan.md` and `product_scope.md` to remove the
missing-access blocker, record absent generated tables and confirm the price rule.
This update completed source review and planning; it did not rebuild data, train
models or execute tests. No team signatures, messages or reported performance
were supplied or asserted on anyone's behalf.


## Confirmed substation product direction — 23 October 2026

The user explicitly confirmed focusing further development on Theo's 2021–2025
substation approach. Defined the final application in `product_scope.md` and removed
the proposed household-pilot view from the remaining plan. Existing household code
and evidence remain historical records; no further household evaluation is planned.
The intended deliverable is a historical-replay forecast, peak-warning and response
scenario dashboard. This update changes scope and documentation, not model code.

## Team document review and revised remaining work — 23 October 2026

Reviewed Theo's 7 October `Closing the Peak Data & Features Explained for the
Team.docx` against the implemented household pipeline. The completed increments
do not implement its revised substation data, weather features or quantile models.
Added `remaining_work_plan.md` to incorporate that direction through functional milestones, with deliverables and acceptance criteria. Identified missing
team project assets, test-period cohort selection and weather-error donor chronology
as integration dependencies. This was a planning/documentation update; no models
were rerun, reported document results adopted, or future milestones marked complete.

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

## Trained forecasts and validation diagnostics — 23 October 2026 (Australia/Sydney)

The user requested completion of the supervised modelling milestone. This entry
uses the actual client date, not the original roadmap's projected calendar date.

### Delivered

- Separate pooled GC/GG XGBoost models using the existing 17-feature allowlist.
- Prespecified three-candidate CPU search per target; seed 2112, four threads.
- GC selected by evening MAE; GG by full-day MAE. Both selected depth 3 / 200 trees.
- Native UBJSON models, hash-checked metadata and exact baseline-mask comparison.
- Reloadable 48-slot forecasts per target, selectable by supported household/date.
- Offline reports with observed/persistence/model traces, time and household errors,
  residual distributions and full-day/evening pooled/community metrics.
- Offline CodeCarbon search estimate with explicit CPU/RAM assumptions and scope.
- Updated package 0.3.0, dependency lock and Mac OpenMP setup instructions.

### Measured results

501,120 validation predictions cover the same fixed 30-household pilot and 174
eligible dates per target as the persistence benchmark. Model fitting uses
744,480 training rows per target. No final-test feature files or observations are
loaded or evaluated by this milestone's model pipeline.

| Target/window | Baseline MAE | XGBoost MAE | MAE improvement |
|---|---:|---:|---:|
| GC full day | 0.189325 | 0.160583 | 15.181545% |
| GC evening | 0.299297 | 0.255154 | 14.748692% |
| GG full day | 0.074690 | 0.056677 | 24.116750% |
| GG evening | 0.034519 | 0.025970 | 24.768010% |

Errors are kWh per half-hour. Evening demand misses the 15% ambition by about
0.25 percentage points. Both larger candidates perform worse on their respective
selection metric; no further search was introduced to force the target. Validation
was used for selection and these improvements are not final-test evidence.

### Executed verification and issues resolved

The independent audit joins all 501,120 actuals and weekly lags to development
source intervals, recomputes all 16 pooled/community metric rows and 240 household
metric rows, reloads native Boosters, and repeats both winning fits. Both refits and
reloads reproduce the complete real validation predictions exactly.

The final automated test count is recorded in `results/evidence/model_tests.json`.
Tests exercise chronological partition checks, leakage provenance, wrong targets,
file tampering, complete 48-slot days, target-independent inputs, deterministic fits,
physical clipping, selection, serialization, carbon failures and end-to-end forecasts.

The initial XGBoost import failed because the Mac lacked OpenMP; `libomp` was
installed and the package imports/trains successfully. A synthetic serialization
test exposed base-score float32 rounding of about 1.2e-7 kWh. The reload invariant
uses an absolute 1e-6 kWh tolerance; real selected-model reloads still match exactly.
CodeCarbon's forced CPU parameter was confirmed to be TDP, with a 50% constant-mode
factor: 15 W input yields 7.5 W effective CPU power, plus assumed 3 W RAM. This is
an estimate, not hardware measurement. Compact final-run values and exclusions are
in `results/evidence/model_carbon.json`; audit refits and earlier development runs
are outside the saved search estimate.

The report and a household/date chart were inspected in the browser, including
horizontal access to solar panels in a narrow viewport. Generated data/models stay
local and ignored by Git; configuration, code and compact evidence are committed.

### Next increment

Transparent pricing and constrained response simulation are next. The integrated
Streamlit application, SHAP and final frozen-method test evaluation remain later
work. Human team review remains pending; no teammate authorship is asserted.

Commit purpose: `feat(ml): implement and evaluate XGBoost forecasting`.
