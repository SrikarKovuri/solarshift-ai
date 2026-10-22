# SolarShift AI — Closing the Peak

An ENGG2112 offline research prototype investigating whether household demand and
PV forecasts can inform transparent pricing and simulated evening load shifting.

**Current increment: forecast-ready features and a measured weekly persistence benchmark.**
Real-data ingestion, temporal feature checks and validation evaluation are operational.
XGBoost, pricing, response simulation, SHAP and the Streamlit application remain
future work. Baseline errors are measured; no model improvement or energy saving is claimed.

Repository: https://github.com/SrikarKovuri/solarshift-ai

## Quick start

Python 3.11–3.13 is permitted by the package; the verified environment is
Python 3.12 on Apple Silicon. Other environments require their own verification.
From this repository directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install .
python -m pytest -q
```

For the exact dependency versions used in the recorded run, install
`requirements-lock.txt` instead of `requirements.txt`.
After modifying source files, reinstall with `python -m pip install --no-deps .`.
For source-tree development without reinstalling, prefix commands with
`PYTHONPATH=src` on macOS/Linux.

## Obtain authentic data

The original Ausgrid download page returned 404 during the feasibility review.
The supported alternative is the archive documented by
[Pierre Haessig](https://github.com/pierre-haessig/ausgrid-solar-data).

```bash
python -m solarshift.data.acquire --config configs/data.toml
```

This downloads the archive, checks the complete ZIP, extracts only the three
annual CSVs and accompanying documentation, and creates `data/raw/acquisition.json`.
A partial archive is rejected; do not rename a failed `.part` download to bypass checks.

Alternatively, supply a complete downloaded archive:

```bash
python -m solarshift.data.acquire --archive /path/to/Ausgrid_solar_home_data.zip
```

Or place these original files in `data/raw/`:

- `Solar home 2010-2011.csv`
- `Solar home 2011-2012.csv`
- `Solar home 2012-2013.csv`

The parser accepts original CSVs directly. File hashes are always recorded, even
when acquisition is manual. See [data provenance](docs/data_provenance.md) for
licensing uncertainty and source limitations. Raw measurements are not committed.

## Prepare and explore

```bash
python -m solarshift.data.prepare --config configs/data.toml
python -m solarshift.data.explore --config configs/data.toml
```

Independently audit the accepted source CSV energy totals against Parquet:

```bash
python scripts/verify_real_data.py --config configs/data.toml
```

The audit also checks interval counts, non-negative finite energy and the kWh-to-kW
relationship across every accepted reading. Its report is saved in `results/evidence/`.

Open `results/generated/household_1_2012-07-01.html` in a browser. The interactive
Plotly chart embeds its JavaScript and works offline. Hover for values, click a
legend to hide/show a channel, and drag to zoom. This is a historical data chart,
not the later Streamlit application.

```bash
python -m solarshift.data.explore --customer 42 --start 2011-01-01 --days 7
```

Configuration paths resolve relative to the parent of `configs/`, so commands
also support an absolute `--config` path. Choose a date between July 2010 and
June 2013. Invalid selections fail with a specific error.

### Generated outputs

| Output | Purpose |
|---|---|
| `data/processed/intervals_YYYY_YYYY.parquet` | Accepted half-hour readings and traceable source keys |
| `data/processed/daily_summary.parquet` | Daily energy and maximum half-hour average power |
| `data/processed/quality_report.json` | Counts, exclusions, warnings, versions and hashes |
| `data/processed/excluded_channel_days.csv` | Each rejected source row and its reasons |
| `data/processed/unavailable_primary_channel_days.csv` | Expected GC/GG dates without an accepted row |
| `data/processed/households.csv` | Validated customer, postcode and capacity metadata |
| `results/generated/*.html` | Self-contained interactive historical chart |
| `results/generated/exploration_summary.json` | Numeric values behind the selected chart |

Three years contain millions of intervals. Processing proceeds one annual file
at a time and writes interval batches to Parquet. Allow several minutes and spare
disk space. Annual CSV parsing still uses memory proportional to one source year.

## Build the forecasting dataset and benchmark

After preparing the original dataset, run:

```bash
python -m solarshift.features.build --config configs/forecast.toml
python -m solarshift.evaluation.baseline --config configs/forecast.toml
python scripts/verify_baseline.py
```

Open `results/generated/baseline/baseline_report.html` for interactive demand/PV
comparisons, error-by-interval and household charts, and full-day/evening tables.
This self-contained report works offline. The default audit script checks the
repository's default experiment paths.

The reproducible pilot contains 30 households chosen using **training coverage
only**, with seed 2112. It is not a representative population sample. The pipeline
creates 1,488,960 training rows and evaluates 501,120 validation rows across GC/GG.
The recorded run has 174 eligible validation days per household/target out of 182.
These counts describe the current data/configuration, not hard-coded targets.

- Forecast issue: 18:00 Australia/Sydney on the preceding calendar day.
- Reading availability: interval end plus 30 minutes (an explicit research assumption).
- Features: calendar cycles, capacity, two-day/weekly lags, seven same-slot readings
  from days -2 through -8, and eligible previous-day values with a two-day fallback.
- Only slots 1–35 of the preceding day are eligible at the default cutoff. The
  availability indicator distinguishes observed previous-day values from fallback.
- Any missing required history excludes the full 48-slot forecast day. Target values
  and provenance columns are excluded from the explicit model-feature list.
- Training: July 2010–December 2011. Validation: January–June 2012.
- Final test: July 2012–June 2013, reserved and not loaded by the feature command.

| Target | Window | Validation MAE (kWh/half-hour) | RMSE (kWh/half-hour) |
|---|---|---:|---:|
| General consumption | Full day | 0.189325 | 0.366841 |
| General consumption | 16:00–21:00 | 0.299297 | 0.503417 |
| Gross PV | Full day | 0.074690 | 0.189625 |
| Gross PV | 16:00–21:00 | 0.034519 | 0.113941 |

These are interval-weighted household errors. Community-sum errors are separate
in the report and require the complete fixed cohort. Night-time PV zeros can make
full-day PV errors appear small; these results are not a daylight-only assessment.
Later XGBoost comparisons must use exactly the same eligibility masks.

Outputs: `data/features/manifest.json`, per-household/target feature Parquet files,
`excluded_forecast_days.csv`, and `results/generated/baseline/` containing predictions,
metrics, household scores, coverage and the HTML report. Compact evidence is
committed under `results/evidence/baseline_*`; large generated files are ignored.

## Interpretation

- **GC**: general consumption; the primary demand definition excludes CL.
- **CL**: controlled load, preserved separately; absent is not assumed zero.
- **GG**: gross PV generation, not measured net exports or battery activity.
- Values are half-hour **kWh**; average **kW = kWh / 0.5**.
- `0:30` is an interval ending; final `0:00` ends the next calendar day.
- Daylight-saving transition days are excluded pending clarification of the
  source's fixed 48-column layout. Gaps remain visible in charts.
- Estimated/non-actual, missing, negative, duplicated and invalid channel-days
  are excluded. No target readings are imputed.

Read [methodology](docs/methodology.md), [limitations](docs/limitations.md),
[architecture](docs/architecture.md), and [development evidence](docs/development_log.md).

## Troubleshooting

- **Missing CSV:** run acquisition or check filenames in `configs/data.toml`.
- **Bad ZIP / incomplete byte count:** retry acquisition; retain the failed file
  only for diagnostics. A local complete archive is also supported.
- **Unexpected columns:** verify that these are the original half-hour CSVs,
  not monthly, transformed or spreadsheet-reformatted files.
- **No accepted readings:** inspect exclusions and try another household/date.
- **Metadata inconsistency:** processing stops rather than silently changing
  customer capacity or location. Investigate source records before proceeding.
- **Dependency installation:** use a fresh environment and supported Python;
  report the actual installation error rather than skipping required packages.

## Team and integrity

Planned roles: Theo Franklin (data/features), Lucas Khanis (modelling), Srikar
Kovuri (evaluation, ethics, integration). These roles do not imply contributions
already performed. Actual AI assistance and human verification are recorded in
[the assistance log](docs/ai_assistance_log.md).

Development proceeds through separately reviewed functional increments.
Commit dates and the development log reflect actual work. Model training starts
only when the next increment is requested.

## Source and software rights

Ausgrid remains the original data source. The mirror states CC BY 3.0 Australia,
but the original licence grant has not independently been recovered. The archive's
original notes permit research use and disclaim representativeness. Do not assume
this repository grants rights over the dataset. No software redistribution licence
is selected on behalf of all team members yet.
