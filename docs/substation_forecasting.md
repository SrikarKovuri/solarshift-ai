# Substation data and forecast integration

Implemented 24 October 2026. This is historical validation replay, with no reserved
load-test scoring. The next milestone is peak warnings and response simulation.

## Executed validation results

| Method | Evening MAE (MW) | Full-day MAE (MW) |
|---|---:|---:|
| Weekly persistence | 1.7593 | 1.4022 |
| Yesterday persistence | 1.2652 | 1.1145 |
| Weather/calendar ridge | 2.0245 | 2.0682 |
| Quantile boosted median | **0.8635** | **0.8251** |

Evening MAE improves **50.92%** against weekly persistence. Raw nominal 80% evening
coverage is **76.84%**; no bootstrap confidence interval or recalibration is claimed.
All methods use the same 848,089 validation intervals (177,536 in the evening).
Training uses 2,084,110 eligible non-anomalous intervals across 63 sites.

**Verification:** 78 tests passed. The independent audit passed source joins,
calendar-day baselines, timestamps, metric recomputation and 10,097 saved-model
sample predictions. There are 15,062 complete eligible site-days for replay.
The example is the first complete site/date: Aberdeen 66_11kV, 1 May 2023.
The observed cleaned-data negative counts rise from 85 before May 2023 to 35,249
from May 2023; this supports a substantial sign-pattern change, not a claim that
all earlier readings were unsigned or that every later negative is solar export.

Compact evidence is in `results/evidence/substation_day4/`; local model/data assets
and `validation_report.html` are in `results/generated/substation_day4/`.
The standalone HTML report was generated; browser preview was unavailable because
the browser blocks local-file URLs. Numeric results were independently audited.

## Reproduce

From the `solarshift-ai` directory, using the pinned project environment:

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 .venv/bin/python -m solarshift.substation.pipeline --source /Users/srikarkovuri/Downloads/ENGG2112_ClosingThePeak --output results/generated/substation_day4
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python scripts/verify_substation.py
```

A normal run rebuilds inputs and refits all three quantile models. Raw source data
remains outside this repository. Generated tables and model files are Git-ignored.
No software installation, network download or source-folder mutation is required.
Use `PYTHONPATH=src` to run the current source rather than the previously installed
household package. Neither the household training nor its final test is rerun.

## Source and implementation

The supplied `ENGG2112_ClosingThePeak` folder is the source of the Ausgrid archives,
weather cache, approximate coordinates, data dictionary, source register and
pre-registration. `source_manifest.json` records SHA-256 hashes of the inputs and
source modules reviewed. The parser, calendar and selection utilities are adapted
from Theo's supplied source; the integration, checks and evidence were implemented
with Codex assistance. These statements do not assign unperformed work to a team
member or imply team sign-off. The standalone assistance log was removed at the
user's request; the development log remains the project history.

Source-register licence claims are supplied metadata, not a new licence grant.
Raw files have not been redistributed. The original source remains unchanged.

## Data and quality contract

- Read FY2021–FY2024 load archives; retain April 2021 burn-in, May 2021–April 2023
  training and May 2023–April 2024 validation. Never open the FY2025 load archive.
- Parse dates explicitly and sort interval-ending columns numerically. A synthetic
  scrambled-column test exercises the FY2025 layout without reading its load data.
- Require MW units and unique site/date rows. Both quarter-hours must be valid;
  half-hour power is their arithmetic mean. Energy is MW multiplied by 0.5 hours.
- Preserve published signed half-hour flow; forecast its absolute magnitude.
  Absolute value is taken after averaging, not before. Pre-May-2023 positive
  published values cannot establish the historical direction of power flow.
- Detect isolated jump-and-return spikes using per-site training median/MAD only.
  Exclude runs of at least 16 identical quarter-hours within each source day.
  This detector does not join flat runs across midnight. Missing values remain missing.
- Exclude both entire DST transition days because the fixed 96-column source
  cannot unambiguously reconstruct autumn's repeated hour. No physical energy total
  is claimed for those days. Flags are 1=missing, 2=spike, 4=flat run, 8=DST.
- Isolation Forest flags possible switching/metering anomalies using training-fitted
  parameters. It is a diagnostic, not proof of switching. Flagged training days
  receive no fitting weight; validation anomalies remain in the evaluation.

## Cohort changes from Theo's reported analysis

Training coverage must reach 90%; validation coverage is descriptive only. Fit
k-means to training weekday/weekend profiles, choose k=2–8 by silhouette, then
choose the residential-like cluster with the largest evening/midday mean ratio
among clusters with evening > midday and weekend/weekday ratio >0.85. Reject
sites with at least 5% flagged training days. This makes the supplied final script's
manual residential-cluster assignment explicit and independent of cluster labels.

This run selects 63 sites, rather than importing the supplied 60-site cohort.
The supplied cohort used test coverage, so its published results are not directly
comparable. Cluster statistics, cohort, coverage and exclusions are exported.
Approximate coordinates/weather zones come from the supplied locations table.

## Availability and features

Issue time is midnight at the start of target day D in Australia/Sydney. All load
lags use calendar-day joins or shifts on a complete daily grid: D−1, D−7, D−14,
preceding seven same-slot values, previous daily mean and previous evening mean.
Missing days cannot silently become yesterday. Static level and evening share use
training only. Calendar and approximate sun position are deterministic.

Weather uses only cached `temperature_2m_previous_day1`, plus its daily min/max/mean.
There is no actual-weather substitution, interpolation, synthetic error donor or
oracle model. Daily weather summaries require all 24 hourly values. The provider
defines this variable as forecast at 24 hours before valid time; the latest forecast
needed for a normal target day is therefore from D−1 at 23:00. See
[Open-Meteo's Previous Runs documentation](https://open-meteo.com/en/docs/previous-runs-api).
The cache has no publication/arrival timestamps. Availability is a documented
historical replay assumption, with one hour for the latest weather value and zero
meter-reading latency at midnight. Operational data latency remains unvalidated.

All five families are retained: historical load, forecast weather, calendar, sun
position and training-derived/site attributes. Humidity, wind, cloud and radiation
are deliberately omitted from this run because their synthetic history uses future
error donors. Feature definitions and exact parameters are saved in `summary.json`.

## Models, metrics and interface

Targets are magnitude divided by each site's training mean. Three XGBoost quantile
models (q10, q50, q90) use 240 trees, depth 5, learning rate 0.05 and seed 2112;
no validation-driven hyperparameter search is performed. Nonnegative clipping and
row-wise sorting repair quantile crossings; all predictions are converted back to
MW before scoring. The published central prediction is the sorted middle value.

Compare weekly persistence, yesterday persistence, standardized ridge regression
on weather/calendar/sun/site attributes and the boosted model on identical eligible
validation rows. Report full-day/evening MAE, RMSE and mean site-normalized absolute
error using training mean as denominator. These are pooled interval metrics, not
network-total forecast errors or equal-weight site averages. Baselines share the
same non-anomalous training population where fitting is required.

The raw q10–q90 band has nominal 80% coverage; it is not yet recalibrated. Final evaluation retains chronological CQR, weekly bootstrap, robustness and final-test freeze work.
No measured response benefit or reproduced Theo headline result is claimed.

`validation_forecasts.parquet` provides site, issue time, interval start/end,
signed actual MW, magnitude actual MW, q10/q50/q90 MW, split, weather provenance,
quality flags and all baseline predictions. `solarshift.substation.forecast.
validation_forecast(directory, site, date)` returns a complete 48-slot replay or
raises a clear unavailable-data error. Actuals are for replay only. Native UBJSON
models, portable ridge coefficients, features, complete-training-evening 90th
percentile thresholds and data audits support the next milestones.

## Verification and remaining work

Tests exercise shuffled interval columns, signed flow and energy units, missing
values, flat runs, spikes, DST, training-only cleaning statistics, duplicate/unit
rejection, reserved dates, future-target perturbation, missing-day lags and absent
weather. The independent audit rejoins actuals and persistence from cleaned source,
reloads native boosters, verifies inverse scaling, and recomputes shared-row metrics.

Peak probabilities, calibration, pricing and energy-conserving response scenarios
are implemented in the response module. Dashboard integration and explanations remain outstanding. Training carbon measurement
has not been recorded for this substation run; the household estimate is not reused.
