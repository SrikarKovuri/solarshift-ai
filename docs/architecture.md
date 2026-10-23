# Architecture and stage boundary

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

Transparent pricing, constrained response, SHAP and the Streamlit interface remain
future work. The model report is a usable research artefact, not the finished app.

## Interval schema

Key: `(customer, source_date, channel, slot)`; slots 1–48.
Fields: `capacity_kwp`, `postcode`, `source_file`, `source_line`,
`energy_kwh`, `average_power_kw`, `interval_start`, `interval_end`.
Timestamps are timezone-aware Australia/Sydney. `source_date` is the source
calendar date, not necessarily the date of `interval_end` at midnight.

GC/GG/CL are separate rows. No export inference, tariff or battery field is fabricated.
Data and generated plots stay outside version control; compact evidence and hashes
are committed so another person can compare a reproduced run.
