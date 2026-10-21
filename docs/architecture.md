# Architecture and stage boundary

Day 1 executable flow:

`complete archive/local CSVs → parse → validate → interval Parquet + audit → historical chart`

`acquire.py` verifies archive completeness/CRC and creates acquisition metadata.
`parse.py` understands the observed annual CSV schema and preserves source lines.
`validate.py` makes conservative row-level decisions and converts interval units.
`prepare.py` orchestrates annual processing, bounded interval batches, checks
cross-year household metadata and publishes outputs only after computation succeeds.
`explore.py` reads only the selected household/date range and creates an offline chart.
`common.py` centralises configuration, SHA-256 and strict JSON output.

The future flow adds cutoff-aware features, temporal splits, persistence,
two XGBoost targets, evaluation, transparent pricing, constrained response,
SHAP and a Streamlit interface. None is represented as working in Day 1.

## Interval schema

Key: `(customer, source_date, channel, slot)`; slots 1–48.
Fields: `capacity_kwp`, `postcode`, `source_file`, `source_line`,
`energy_kwh`, `average_power_kw`, `interval_start`, `interval_end`.
Timestamps are timezone-aware Australia/Sydney. `source_date` is the source
calendar date, not necessarily the date of `interval_end` at midnight.

GC/GG/CL are separate rows. No export inference, tariff or battery field is fabricated.
Data and generated plots stay outside version control; compact evidence and hashes
are committed so another person can compare a reproduced run.
