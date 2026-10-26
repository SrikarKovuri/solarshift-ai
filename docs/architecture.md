# Architecture and stage boundary

The user confirmed the substation pivot on 23 October 2026. The target application
is described in [product scope](product_scope.md) and its implementation sequence
in [remaining work](remaining_work_plan.md). The architecture below documents the
existing household pilot, retained as history; it is not the target data schema.

## Implemented substation path (forecast integration)

`Theo's FY2021–FY2024 sources → training-fitted cleaning → training-selected residential cohort → five feature families → fixed quantile models + three baselines → common validation replay schema`

`substation/pipeline.py` builds development data and models without loading FY2025
load observations. `ausgrid.py`, `calendar_nsw.py` and `selection.py` are adapted
source utilities. `substation/forecast.py` returns complete validation days for the
implemented dashboard; `scripts/verify_substation.py` independently checks the evidence.
See [Forecast integration](substation_forecasting.md) for schema, commands, quality flags and deviations.
The forecast target is magnitude in MW; measured signed flow is a separate field.

## Implemented warning and scenario path (response simulation)

`Forecast validation artifacts + fixed training thresholds → evening risk heuristic → early-validation isotonic calibration → later-validation warning evaluation → constrained signed-flow scenarios`

`substation/response.py` supplies the explicit probability/price formulas and bounded
energy shifting. `substation/day5.py` executes calibration, evaluations and sensitivity
sweeps. `substation/scenario_replay.py` returns a complete site/date journey for dashboard integration.
`scripts/verify_day5.py` independently verifies saved evidence and the replay API.

## Implemented application and explanations

`streamlit_app.py` connects the complete-day catalog, replay API and evidence tables.
`substation/dashboard.py` keeps magnitude forecasts separate from signed-flow charts.
`substation/explain.py` reloads the fixed models for later-validation grouped
permutation importance; `scripts/verify_day6.py` independently matches its sampled
loss to saved predictions and verifies the scenario catalog. No training or reserved
observations are loaded by the interactive application. See [dashboard guide](dashboard.md).

## Archived household path

Data foundation:

`complete archive/local CSVs → parse → validate → interval Parquet + audit → historical chart`

`acquire.py` verifies archive completeness/CRC and creates acquisition metadata.
`parse.py` understands the observed annual CSV schema and preserves source lines.
`validate.py` makes conservative row-level decisions and converts interval units.
`prepare.py` orchestrates annual processing, bounded interval batches, checks
cross-year household metadata and publishes outputs only after computation succeeds.
`explore.py` reads only the selected household/date range and creates an offline chart.
`common.py` centralises configuration, SHA-256 and strict JSON output.

Forecasting foundation:

`validated intervals → training-only cohort → cutoff-aware features → train/validation partitions → weekly persistence → validation metrics + interactive report`

`features/dataset.py` defines feature columns, calendar lookups, timestamp provenance
and split membership. `features/build.py` verifies input hashes and writes only
development datasets. `models/persistence.py` predicts the seven-day lag.
`evaluation/metrics.py` defines physical-unit metrics and complete-cohort aggregation;
`evaluation/baseline.py` verifies feature hashes and evaluates validation only.

Supervised forecasting:

`verified development features → bounded two-target CPU search → validation selection → native model files → reload and compare → day forecast / diagnostic report`

`models/boosted.py` checks inputs, feature order, model hashes and forecast days.
`models/train.py` fits three configurations for each target with training-only rows;
`models/tracking.py` records the search's offline carbon estimate. `evaluation/boosted.py`
reproduces forecasts and checks exact baseline eligibility before reporting metrics.
`models/forecast.py` produces 48 half-hours per target for a supported validation day.
`scripts/verify_models.py` independently verifies source joins, metrics and repeat fits.

This household branch is archived and is not loaded by the current application.

## Interval schema

Key: `(customer, source_date, channel, slot)`; slots 1–48.
Fields: `capacity_kwp`, `postcode`, `source_file`, `source_line`,
`energy_kwh`, `average_power_kw`, `interval_start`, `interval_end`.
Timestamps are timezone-aware Australia/Sydney. `source_date` is the source
calendar date, not necessarily the date of `interval_end` at midnight.

GC/GG/CL are separate rows. No export inference, tariff or battery field is fabricated.
Data and generated plots stay outside version control; compact evidence and hashes
are committed so another person can compare a reproduced run.
