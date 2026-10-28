# Reproducing the research

For immediate assessment use `python run.py`; see marker_guide.md. This document
covers full training/evaluation, which is substantially larger than the walkthrough.

## Source folder

Supply a source directory containing:

- `data/raw/ausgrid/ausgrid_zss_FY2021.zip` through `ausgrid_zss_FY2025.zip` from Ausgrid.
- `data/raw/weather/openmeteo_<zone>__gfs_dayahead.csv` for the six selected weather
  zones, from the original Previous Runs cache documented in the source manifest.
- `data/processed/substation_locations.csv`, the approximate location/zone mapping.
- `reports/data_dictionary.md`, `reports/data_sources.md`, `reports/preregistration.md`
  and the supplied reference `src/*.py` files for source-hash provenance.

These are the team handover inputs, not hidden marker prerequisites. The public
walkthrough is independently runnable without this folder. Exact research input
hashes are recorded in results/evidence/substation_day4/source_manifest.json and
final_evaluation/summary.json. Provider updates can prevent byte-identical retraining.

## Development sequence

Install requirements and `python -m pip install --no-deps -e .`, then run:

```sh
python -m solarshift.substation.pipeline --source /path/to/source
python scripts/verify_substation.py
python -m solarshift.substation.day5
python scripts/verify_day5.py
python -m solarshift.substation.explain
python scripts/verify_day6.py
python -m solarshift.substation.evaluate
python -m solarshift.substation.robustness
python -m pytest -q
```

Do not overwrite the original research outputs to try new parameters. Use a separate
checkout/output directory and label any new experiment. Native frozen UBJSON models
are retained in artifacts/frozen_models for inspection and inference.

## Final test

The final test has already been executed. Its result is retained, not rerun during
app startup or marker setup. The historical invocation was:

```sh
python -m solarshift.substation.final_evaluation --source /path/to/source --approval "Human approval record"
python scripts/verify_final.py
```

The command requires an exclusive new freeze/run record and refuses existing files.
Its implementation is retained for audit. Running altered methods after seeing the
published test results is a new, disclosed analysis, not another untouched holdout.
See final_evaluation.md for the local freeze's differences from the reference plan.
